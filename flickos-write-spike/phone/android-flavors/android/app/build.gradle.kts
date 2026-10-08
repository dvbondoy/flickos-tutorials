plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "io.github.dvbondoy.flickos_notes"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "io.github.dvbondoy.flickos_notes"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildFeatures {
        buildConfig = true
    }

    // Two apps from one repository (flickos-write ADR-008): each flavor has
    // its own application id, name and link scheme. Notes keeps its id, so
    // the installed Notes app updates in place.
    flavorDimensions += "app"
    productFlavors {
        create("notes") {
            dimension = "app"
            applicationId = "io.github.dvbondoy.flickos_notes"
            manifestPlaceholders["appLabel"] = "Notes"
            manifestPlaceholders["linkScheme"] = "flicknotes"
            buildConfigField("String", "LINK_SCHEME", "\"flicknotes\"")
        }
        create("write") {
            dimension = "app"
            applicationId = "io.github.dvbondoy.flickos_write"
            manifestPlaceholders["appLabel"] = "Write"
            manifestPlaceholders["linkScheme"] = "flickwrite"
            buildConfigField("String", "LINK_SCHEME", "\"flickwrite\"")
        }
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
