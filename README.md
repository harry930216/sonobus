# SonoBus G8X（非官方修改版）

這是 [SonoBus](https://github.com/sonosaurus/sonobus) 1.7.2 的個人修改版，與 Sonosaurus 官方無關。官方版本請到原專案；原專案的說明保留在 [README_SONOBUS.md](README_SONOBUS.md)。修改日期：2026-11-14～15（詳細改動見 `g8x-quaddac` 分支的 commit 紀錄）。

> Unofficial personal fork of SonoBus 1.7.2 for playing PC audio through the LG G8X Quad DAC and controlling the phone volume from the desktop. Not affiliated with Sonosaurus. The original SonoBus README is kept in [README_SONOBUS.md](README_SONOBUS.md).

目的：把電腦正在播放的任何聲音，以未壓縮的 PCM 即時送到 LG G8X ThinQ，由手機內建的 ESS Quad DAC（數位類比轉換晶片）轉成類比訊號，再接有線耳機；並且從電腦調整手機的音量。

## 改了什麼

### 手機輸出走 Quad DAC
- Android 的 Oboe 輸出改成 `PerformanceMode::PowerSaving`、共用模式、用途標成媒體（`deps/juce/.../juce_Oboe_android.cpp`）。
- 原因：G8X 上低延遲的 `PRIMARY|FAST` 輸出不經過 Quad DAC；`DEEP_BUFFER`（深緩衝）輸出才會經過。用 `adb shell dumpsys media.audio_flinger` 確認過。

### 從電腦調手機音量
- 電腦版：視窗底部的「Phone Vol」調整條，以及 Windows 系統匣的喇叭圖示（點一下跳出小調整條）。
- 指令走 SonoBus 原本的聊天訊息通道：電腦送 `/vol =N`，手機回 `[vol] 4/75 (5%) hifi cap9`；這些訊息不會出現在聊天框。不另開網路連接埠。
- LG 的媒體音量內部是 75 段，第三方 App 用標準 API 只拿得到 15 段。做法是呼叫公開的 `setStreamVolume` 時帶上 LG 的旗標 `0x20000`；目前格數從 `Settings.System` 的 `volume_music_headphone` 讀取。
- 安全設計（耳機很敏感時用）：
  - 手機端寫死上限：遠端指令最多調到第 9 格（`sbRemoteVolumeCap75`），可依自己的耳機修改。
  - 一次往上超過 5 格的指令，要在電腦上按確認才會送出；手機端也會檢查，沒有確認記號的直接拒絕。
  - 剛調完音量、系統設定還沒更新時，手機用即時的 15 段讀數判斷目前的音量，不會因為讀到舊值而誤判成「調低」。
  - 75 段的寫法只在驗證過的 G8X（型號 `LM-G850`）上啟用；其他手機改用標準的 15 段 API。
  - 寫入後立刻讀回，如果系統沒照 75 段處理，馬上改回原本的音量。
  - 不是數字的參數一律不動作。
  - 手機上自己調音量（例如 LG 萬用觸控）不受上限限制。
- `tools/g8x_volume.pyw`：用 adb（要接 USB）調音量的小工具，是較早的做法。adb 路徑寫在 `tools/adb_path.txt`（不進版本控制），沒有這個檔就用 PATH 上的 `adb`。

### 其他
- CMake：旁邊沒有 Steinberg ASIO SDK 時，自動不編譯 ASIO 支援。
- Android：套件名稱 `com.sonosaurus.sonobus.g8x`（可以跟官方版並存）、App 名稱「SonoBus G8X」、用除錯金鑰簽章、只編 arm64。

## 限制

- 手機端最後是 16 位元 48 kHz：`DEEP_BUFFER` 的硬體格式是 16 位元，而且音量是在轉成 16 位元之前於數位端調整。
- 第三方 App 在 G8X 的 Android 12 上，用公開 API 分配不到 24／32 位元的 `direct_pcm` 直通輸出。實測過 32 位元整數輸出、384 kHz 取樣率、卸載播放（offloaded playback），都還是進混音器。所以電腦端傳 PCM 16 就夠了。
- 延遲大約 0.3～0.45 秒（網路緩衝加手機深緩衝，推算值）。
- 音量相關的行為只在 LG G8X（Android 12）上驗證過。

## 建置

### Windows（電腦版）
需要 Visual Studio 2022 Build Tools（C++ 桌面開發）。

```
cmake -G "Visual Studio 17 2022" -A x64 -B build
cmake --build build --config Release --target SonoBus_Standalone
```

產物在 `build/SonoBus_artefacts/Release/Standalone/SonoBus.exe`。

### Android（手機版）
需要 JDK 17 和 Android SDK。在 `mobile/Builds/Android/local.properties` 設定 `sdk.dir`。這個檔被上游追蹤，裡面會有你的本機路徑；改完先執行 `git update-index --skip-worktree mobile/Builds/Android/local.properties`（讓 git 忽略這個檔的本機修改），以免不小心 commit 出去。然後：

```
cd mobile/Builds/Android
gradlew assembleRelease_Release
```

產物在 `app/build/outputs/apk/release_/release/`。

## 授權

跟 SonoBus 相同：GPLv3，加上原專案的 App Store 例外條款（見 `LICENSE`、`LICENSE_EXCEPTION`）。SonoBus 原作者是 Jesse Chappell。
