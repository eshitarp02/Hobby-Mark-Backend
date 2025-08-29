package com.moodmark.app.network

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query
import retrofit2.Call

// Data classes for requests and responses

data class ActivityLogRequest(
    val user_id: String,
    val timestamp: String,
    val activity_type: String,
    val title: String,
    val description: String? = null,
    val bookmark: String? = null
)

data class LogResponse(val message: String?, val error: String?)
data class SuggestionResponse(val suggestion: String?, val error: String?)

interface MoodMarkApi {
    @POST("/log-activity")
    fun logActivity(@Body activity: ActivityLogRequest): Call<LogResponse>

    @GET("/get-suggestion")
    fun getSuggestion(@Query("user_id") userId: String): Call<SuggestionResponse>
}

object ApiClient {
    private const val BASE_URL = "https://your-api-gateway-url.amazonaws.com/prod" // Replace with your API Gateway URL

    val instance: MoodMarkApi by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(MoodMarkApi::class.java)
    }
}
