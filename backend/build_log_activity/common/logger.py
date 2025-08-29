"""
Structured logging for AWS Lambda handlers.

Usage:
    from common.logger import get_logger, with_logging
    logger = get_logger(__name__)
    @with_logging()
    def handler(event, context):
        ...

Env Vars:
    LOG_LEVEL=DEBUG|INFO|WARNING|ERROR
    LOG_SENSITIVE_FIELDS=authorization,cookie,token,password (overrides/adds)
    LOG_JSON=true|false
"""
import logging
import os
import sys
import json
import time
import traceback
from datetime import datetime
from functools import wraps
from typing import Any, Callable, List

_DEFAULT_MASK_FIELDS = [
    "password", "passwd", "token", "access_token", "refresh_token", "authorization",
    "cookie", "set-cookie", "api_key", "secret", "ssn", "email"
]

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "level": record.levelname,
            "ts": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "message": record.getMessage(),
            "logger": record.name,
        }
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log.update(record.extra)
        return json.dumps(log)

def get_logger(name: str = "app") -> logging.Logger:
    logger = logging.getLogger(name)
    if not getattr(logger, "_structured", False):
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))
        handler = logging.StreamHandler(sys.stdout)
        if os.getenv("LOG_JSON", "true").lower() == "true":
            handler.setFormatter(JsonFormatter())
        else:
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        # Remove duplicate handlers
        logger.handlers = []
        logger.addHandler(handler)
        logger._structured = True
    return logger

def mask_pii(data: Any, fields: List[str]) -> Any:
    if not fields:
        fields = _DEFAULT_MASK_FIELDS
    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            if any(f.lower() == k.lower() for f in fields):
                masked[k] = "***MASKED***"
            else:
                masked[k] = mask_pii(v, fields)
        return masked
    elif isinstance(data, list):
        return [mask_pii(item, fields) for item in data]
    return data

def _get_mask_fields() -> List[str]:
    env_fields = os.getenv("LOG_SENSITIVE_FIELDS", "")
    fields = _DEFAULT_MASK_FIELDS.copy()
    if env_fields:
        for f in env_fields.split(","):
            f = f.strip()
            if f and f.lower() not in [x.lower() for x in fields]:
                fields.append(f)
    return fields

def with_logging(handler=None, *, mask_fields: List[str] = None):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(event, context, *args, **kwargs):
            logger = get_logger(func.__module__)
            start = time.time()
            req_id = getattr(context, "aws_request_id", None)
            func_name = getattr(context, "function_name", None)
            func_ver = getattr(context, "function_version", None)
            trace_id = None
            headers = event.get("headers", {}) if isinstance(event, dict) else {}
            if isinstance(headers, dict):
                trace_id = headers.get("X-Amzn-Trace-Id")
            mask_fields_eff = mask_fields or _get_mask_fields()
            # Event summary
            route = event.get("path") if isinstance(event, dict) else None
            method = event.get("httpMethod") if isinstance(event, dict) else None
            qs = event.get("queryStringParameters") if isinstance(event, dict) else None
            path_params = event.get("pathParameters") if isinstance(event, dict) else None
            body = event.get("body") if isinstance(event, dict) else None
            is_base64 = event.get("isBase64Encoded") if isinstance(event, dict) else False
            body_len = len(body) if isinstance(body, str) else 0
            event_summary = {
                "route": route,
                "method": method,
                "qs": len(qs) if qs else 0,
                "pathParams": list(path_params.keys()) if path_params else [],
                "body_len": body_len,
                "is_base64": bool(is_base64)
            }
            # Mask and truncate body
            masked_body = None
            full_body = body
            if is_base64:
                masked_body = None
            elif body and body_len <= 4096:
                try:
                    parsed = json.loads(body)
                    masked_body = json.dumps(mask_pii(parsed, mask_fields_eff))[:512]
                    if body_len > 512:
                        masked_body += "...truncated"
                except Exception:
                    masked_body = body[:512] + ("...truncated" if body_len > 512 else "")
            else:
                masked_body = None
            event_summary["masked_body"] = masked_body
            event_summary["full_body"] = full_body
            logger.info("request_received", extra={
                "extra": {
                    "func": func_name,
                    "version": func_ver,
                    "requestId": req_id,
                    "traceId": trace_id,
                    "event_summary": event_summary
                }
            })
            try:
                response = func(event, context, *args, **kwargs)
                duration = int((time.time() - start) * 1000)
                # Response summary
                status_code = response.get("statusCode") if isinstance(response, dict) else None
                resp_body = response.get("body") if isinstance(response, dict) else None
                resp_headers = response.get("headers") if isinstance(response, dict) else None
                resp_body_len = len(resp_body) if isinstance(resp_body, str) else 0
                resp_summary = {
                    "statusCode": status_code,
                    "body_len": resp_body_len,
                    "headers_keys": list(resp_headers.keys()) if resp_headers else []
                }
                # Log full response body for development
                logger.info("response_sent", extra={
                    "extra": {
                        "func": func_name,
                        "version": func_ver,
                        "requestId": req_id,
                        "traceId": trace_id,
                        "duration_ms": duration,
                        "response_summary": resp_summary,
                        "response_payload": resp_body
                    }
                })
                return response
            except Exception as e:
                duration = int((time.time() - start) * 1000)
                logger.error("handler_exception", extra={
                    "extra": {
                        "func": func_name,
                        "version": func_ver,
                        "requestId": req_id,
                        "traceId": trace_id,
                        "duration_ms": duration,
                        "exception_type": type(e).__name__,
                        "exception_message": str(e),
                        "stack": traceback.format_exc()
                    }
                })
                raise
        return wrapper
    return decorator(handler) if handler else decorator
