package com.auramusic.wiki

import android.content.Context
import com.auramusic.wiki.data.NeteaseSession
import com.auramusic.wiki.data.NosUploader
import com.auramusic.wiki.data.WikiApi

/** 应用级单例：登录会话、接口与上传。 */
class AppGraph private constructor(context: Context) {
    val session = NeteaseSession(context)
    val api = WikiApi(session)
    val uploader = NosUploader(context, session)
    val prefs = context.getSharedPreferences("public_wiki_queries", Context.MODE_PRIVATE)
    val drafts = context.getSharedPreferences("artist_wiki_drafts", Context.MODE_PRIVATE)

    companion object {
        @Volatile
        private var instance: AppGraph? = null

        fun get(context: Context): AppGraph = instance ?: synchronized(this) {
            instance ?: AppGraph(context.applicationContext ?: context).also { instance = it }
        }
    }
}
