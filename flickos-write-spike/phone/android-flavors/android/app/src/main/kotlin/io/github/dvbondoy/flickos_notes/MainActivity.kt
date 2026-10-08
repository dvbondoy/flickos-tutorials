package io.github.dvbondoy.flickos_notes

import android.content.Intent
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * Hands flicknotes:// addresses to Dart (the design's ADR-004), Dart's text to
 * Android's share sheet, and the app's private folder to Dart. No plugin: a
 * channel of our own does all three.
 *
 * Dart asks for the address the app was opened with ("initialLink", once);
 * an address arriving while the app runs comes as "link".
 */
class MainActivity : FlutterActivity() {
    private var channel: MethodChannel? = null
    private var initialLink: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        // Recreated after Android stopped the app: its intent was handled then.
        if (savedInstanceState == null) initialLink = linkOf(intent)
        super.onCreate(savedInstanceState)
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        channel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).apply {
            setMethodCallHandler { call, result ->
                when (call.method) {
                    "initialLink" -> {
                        result.success(initialLink)
                        initialLink = null
                    }
                    // The app's private folder, where the notes are (no path_provider:
                    // on Android it now pulls in package:jni and a C build).
                    "filesDir" -> result.success(filesDir.absolutePath)
                    // spike 1: hand text straight to one app (KDE Connect), no chooser
                    "shareTo" -> {
                        val send = Intent(Intent.ACTION_SEND).apply {
                            type = "text/plain"
                            putExtra(Intent.EXTRA_TEXT, call.argument<String>("text") ?: "")
                            setPackage(call.argument<String>("package"))
                        }
                        try {
                            startActivity(send)
                            result.success(null)
                        } catch (e: Exception) {
                            result.error("share", e.toString(), null)
                        }
                    }
                    "share" -> {
                        share(call.argument<String>("title") ?: "", call.argument<String>("text") ?: "")
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        linkOf(intent)?.let { channel?.invokeMethod("link", it) }
    }

    private fun linkOf(intent: Intent?): String? =
        if (intent?.action == Intent.ACTION_VIEW && intent.data?.scheme == SCHEME) intent.dataString else null

    private fun share(title: String, text: String) {
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, title)
            putExtra(Intent.EXTRA_TEXT, text)
        }
        startActivity(Intent.createChooser(send, title))
    }

    companion object {
        const val CHANNEL = "flickos_notes/links"
        val SCHEME: String = BuildConfig.LINK_SCHEME
    }
}
