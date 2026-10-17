<div align="center">

# bambu-slicer-sweep

[English](README.md) · **繁體中文**

用 Bambu Studio CLI 對 3MF 自動掃描稀疏填充密度（與填充圖案），彙整用料、時間與各走線類型用量，找出最省料的設定。

[使用說明](docs/usage.md) · [設計說明](docs/design.md) · [CLI 與 GUI 數據對照](docs/verification.md) · [葉片掃描結果](results/blade_gyroid_density_5-15/summary.txt)

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![Bambu Studio](https://img.shields.io/badge/Bambu%20Studio-2.7.1.62-00AE42)
![Platform](https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white)
![Tests](https://img.shields.io/badge/tests-unittest-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

</div>

```text
> python -m slicer_sweep "input/model.3mf" --range 5 15 1

密度  總用料 g  稀疏填充 g  橋接 g  稀疏+橋接 g  內部實心 g      總時間  標記
----  --------  ----------  ------  -----------  ----------  ----------  -------------------
5%      114.67        6.64   45.48        52.12       31.69   4h 31m 1s
6%      117.83        7.79   47.65        55.44       31.53  4h 37m 13s
7%      106.65        9.35   35.03        44.39       31.39  4h 17m 11s
8%      105.17       10.86   32.34        43.20       31.10  4h 15m 27s
9%      113.27       11.93   39.44        51.37       31.03  4h 30m 33s
10%     106.74       13.56   29.85        43.41       32.46  4h 16m 23s
11%     102.45       15.29   25.06        40.35       31.24  4h 10m 23s  ★最少用料 ⏱最短時間
12%     110.71       16.20   32.45        48.64       31.20  4h 25m 48s
13%     105.31       17.81   25.64        43.45       31.00  4h 15m 40s
14%     106.15       18.92   25.27        44.19       31.10  4h 17m 30s
15%     106.75       20.41   24.28        44.69       31.19   4h 20m 9s

總用料最少：11%（102.45 g，4h 10m 23s）
時間最短：11%（102.45 g，4h 10m 23s）
```

## ✨ 功能

- 直接使用 3MF 內嵌的印表機／耗材／工藝設定，只以命令列參數覆蓋要掃描的值
- 密度可用清單或範圍＋步長，支援小數（例如 `10.5`）
- 可同時掃描多種填充圖案，也可用 `--set` 固定覆蓋其他設定
- 依 G-code 的 `; FEATURE:` 計算各走線類型用量，換算方式與 GUI 一致（[對照結果](docs/verification.md)全部在 0.2% 以內）
- 輸出 CSV＋終端機摘要，標出總用料最少與時間最短的組合，並列出「稀疏填充＋橋接」
- 每次切片後讀回 G-code 中的設定，確認覆蓋真的有套用

## 🚀 快速開始

需求：Windows、Python 3.14、Bambu Studio 2.7（預設路徑 `C:\Program Files\Bambu Studio\bambu-studio.exe`）。只用標準函式庫，不需安裝套件；在專案資料夾中執行即可。
以下範例假設 3MF 放在 `input\model.3mf`（`input\` 不會進 git），也可以直接給任何路徑。

```powershell
python -m slicer_sweep "input\model.3mf" --range 5 15 1
```

## 📖 使用方式

```powershell
python -m slicer_sweep <3MF 路徑> <密度指定> [選項]
```

`<密度指定>` 必填，用 `-d` 或 `-r`（可併用）。其餘都是選項：

| 參數 | 預設 | 說明 |
|---|---|---|
| `-d 3,10.5,11` | — | 密度清單（%），逗號分隔，可用小數 |
| `-r 5 15 1` | — | 密度範圍：起始、結束、步長，**包含結束值** |
| `-p gyroid,grid` | 3MF 內嵌的圖案 | 填充圖案（Bambu 設定值，例如 `gyroid`、`grid`、`cubic`、`adaptivecubic`、`honeycomb`、`lightning`），每個圖案都跑完所有密度 |
| `--set wall_loops=3` | — | 所有切片都固定覆蓋的其他設定，可重複 |
| `--plate 2` | `1` | 盤號 |
| `-o results\xxx` | `results\<模型名>_<時間>` | 輸出資料夾 |
| `--keep` | 不保留 | 保留每次切片的 `.gcode.3mf` |
| `--timeout 600` | `300` | 每次切片的逾時秒數 |
| `--exe 路徑` | `C:\Program Files\Bambu Studio\bambu-studio.exe` | Bambu Studio 執行檔 |
| `--lang en` | 依 Windows 顯示語言 | 輸出語言：`zh-TW` 或 `en` |

常見用法：

```powershell
# 指定幾個密度（可用小數）
python -m slicer_sweep "input\model.3mf" -d 3,10.5,11,13

# 8%～14% × 三種圖案（共 21 次），保留 gcode.3mf，輸出到指定資料夾
python -m slicer_sweep "input\model.3mf" -r 8 14 1 -p gyroid,grid,cubic --keep -o results\patterns

# 第 2 盤，牆數固定為 3，逾時改為 10 分鐘
python -m slicer_sweep model.3mf --plate 2 -d 10,15 --set wall_loops=3 --timeout 600
```

輸出資料夾中有 `sweep.csv`（每次切片一列）、`summary.txt`（與終端機相同的摘要表），加 `--keep` 時另有每次的 `.gcode.3mf`。
全部成功時結束代碼為 0，有任何一次失敗為 1，參數錯誤為 2。

完整說明（密度寫法、圖案名稱對照、小數密度注意事項、常見錯誤訊息）見 **[docs/usage.md](docs/usage.md)**。

<details>
<summary>CSV 欄位說明</summary>

重量單位皆為 g，以 3MF 中耗材的密度與線徑換算；各走線類型與 GUI 預覽「走線類型」統計相同。

| 欄位 | 說明 |
|---|---|
| `pattern` | 填充圖案（從 G-code 讀回的實際值） |
| `density_pct` | 稀疏填充密度（%） |
| `status` | `ok` 或 `error` |
| `total_g` | 總用料（切片器計算值，同 GUI） |
| `sparse_plus_bridge_g` | 稀疏填充＋橋接 |
| `sparse_infill_g` | 稀疏填充 |
| `bridge_g` | 橋接（含內部橋接） |
| `internal_solid_infill_g` | 內部實心填充（含 G-code 中的 `Floating vertical shell`） |
| `top_surface_g` / `bottom_surface_g` | 頂面／底面 |
| `inner_wall_g` / `outer_wall_g` | 內牆／外牆 |
| `gap_infill_g` | 填縫 |
| `custom_g` | 自定義（起始 G-code 的劃線等） |
| `other_g` | 上列以外的類型（例如支撐） |
| `filament_m` | 線材長度（m） |
| `total_time` / `total_time_s` | 總時間（含準備時間），文字與秒數 |
| `print_time` | 模型列印時間（不含準備時間） |
| `slice_seconds` | 這次切片花了幾秒 |
| `gcode_3mf` | 有 `--keep` 時保留的檔名 |
| `error` | 失敗原因 |

CSV 以 UTF-8（含 BOM）寫出，可直接用 Excel 開啟。

</details>

## 🔒 安全性

- 原始 3MF 不會被修改：先複製到輸出資料夾的 `_work\` 再切片，結束後刪除暫存
- 不讀取 `%AppData%\BambuStudio` 或安裝資料夾，所有設定都來自 3MF
- 一次只執行一個切片程序；逾時會結束整個程序樹，切片器結束後程序清不掉時也會自動偵測並繼續
- 按 Ctrl+C 中斷時會先結束切片程序

## 🧪 開發

```powershell
python -m unittest discover -s tests -t .
```

與 GUI 實測數據對照（會切 13 次，重新產生 [docs/verification.md](docs/verification.md)）：

```powershell
python tools\verify_gui.py "input\model.3mf"
```

<details>
<summary>專案結構</summary>

```text
slicer_sweep/
  cli.py           命令列參數、終端機摘要表
  sweep.py         掃描流程、CSV、最佳值
  bambu.py         執行 bambu-studio.exe（逾時、結束程序樹）
  _launch.py       在隱藏主控台中啟動切片器，偵測程序清不掉的狀況
  sliced.py        讀取 gcode.3mf：標頭、設定、耗材密度
  gcode_stats.py   依 ; FEATURE: 加總各走線類型的擠出長度
  i18n.py          中英文訊息
tests/             單元測試
tools/
  verify_gui.py       CLI 與 GUI 數據對照
  capture_console.py  擷取 bambu-studio --help（它只寫到主控台）
docs/              設計說明、驗證結果、CLI --help 輸出
results/           掃描結果
```

</details>

## 📚 文件

- [使用說明](docs/usage.md)：所有參數、圖案名稱對照、輸出與錯誤訊息
- [設計說明](docs/design.md)：為什麼用命令列覆蓋、G-code 怎麼換算、程序管理
- [CLI 與 GUI 數據對照](docs/verification.md)
- [Bambu Studio 2.7.1.62 `--help` 輸出](docs/bambu-cli-help.txt)

## ⚠️ 限制

- 只支援 Windows（用到 `taskkill` 與 Windows 的程序群組），只在 Bambu Studio 2.7.1.62 上驗證過
- 參數名稱必須是 Bambu 的設定鍵；名稱或值無效時切片器只回傳 exit code -2，不會說明原因
- 只驗證 `sparse_infill_density` 與 `sparse_infill_pattern` 有套用；`--set` 的其他設定不會讀回檢查
- 若 3MF 中有物件／零件層級的填充設定，命令列覆蓋可能不會套用到該物件（工具會警告）
- 多耗材的 3MF：各走線類型的重量一律用第 1 個耗材的密度與線徑換算（總用料仍是切片器的正確值）
- 時間是切片器的估算值，與 GUI 相同，但不等於實際列印時間
- 約 2～5% 的切片，切片器正常結束後 Windows 卻清不掉它的程序（推測與顯示卡驅動有關）。結果不受影響，但那次的暫存資料夾要重新開機後才能刪除，工具會提示。詳見[設計說明](docs/design.md#切片器結束了卻清不掉)
- 小數密度（例如 10.5%）CLI 會照實使用，但 GUI 中不一定能輸入同樣的值；要列印時請用 `--keep` 保留的 gcode.3mf

## 授權

[MIT](LICENSE)
