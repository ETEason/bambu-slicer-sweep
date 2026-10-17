# 設計說明

## 為什麼用命令列參數覆蓋，而不是修改 3MF

Bambu Studio 2.7.1.62 的 CLI 接受以設定鍵名覆蓋單一設定，優先順序高於 3MF 內嵌設定：

```
bambu-studio --sparse-infill-density 10.5% --slice 1 --export-3mf out.gcode.3mf model.3mf
```

實測結果（見 [bambu-cli-help.txt](bambu-cli-help.txt) 與 [verification.md](verification.md)）：

| 寫法 | 結果 |
|---|---|
| `--sparse-infill-density 3%`（連字號） | 成功，G-code 的 CONFIG 區塊為 `sparse_infill_density = 3%` |
| `--sparse-infill-density 3`（不帶 %） | 成功，同上 |
| `--sparse-infill-density 10.5%`（小數） | 成功 |
| `--sparse-infill-pattern grid` | 成功 |
| `--sparse_infill_density 3%`（底線） | 失敗，exit code -2，沒有任何輸出 |
| 不存在的圖案名稱 | 失敗，exit code -2 |

所以不需要複製並改寫 3MF 的 `project_settings.config`。其他設定都維持 3MF 內嵌值，
也不必讀取 `%AppData%\BambuStudio` 中的預設檔。工具仍會先把 3MF 複製到輸出資料夾的 `_work/`
再交給切片器，原始檔不會被碰到。

每次切片後，工具會從輸出 G-code 的 `; CONFIG_BLOCK` 讀回 `sparse_infill_density` /
`sparse_infill_pattern`，和要求的值不符時就把該次標為失敗，不會默默用錯誤的設定。

## 為什麼自己解析 G-code

切片器只在 `result.json` 和 G-code 標頭提供總重量與總時間。各走線類型的用量要自己從 G-code 算：

- 依 `; FEATURE: <類型>` 註解分段。
- 只計算「有 X/Y/Z 移動且 E 增加」的指令；純 E 指令（回抽、回抽補償、沖刷）不計入任何類型。
  這和 GUI 的 GCodeProcessor 一致：起始 G-code 中帶 XY 的劃線 30.04 mm 正好是 GUI 的「自定義 0.09 g」。
- 支援 `M82` / `M83` / `G92`，以及 `G2` / `G3` 圓弧。
- 重量 = 長度 × π × (線徑/2)² × 密度。線徑與密度從切片後 3MF 的 `filament_diameter`、
  `filament_density` 讀取，不寫死。
- `Floating vertical shell` 是 G-code 中的獨立類型，但 GUI「走線類型」沒有這一列；
  它的用量加上 `Internal solid infill` 正好等於 GUI 的「內部實心填充」，所以併入該類。

各類型的加總長度與 G-code 標頭的 `total filament length` 完全一致；若不一致，工具會發出警告。

## 程序管理與逾時

- 一次只啟動一個 `bambu-studio.exe`，逾時預設 300 秒。
- `bambu-studio.exe` 會附加到**父程序**的主控台並把記錄（`[trace]`、`ZFiller: …` 等）寫在那裡，
  重新導向 stdout/stderr、`DETACHED_PROCESS`、`CREATE_NO_WINDOW`、`CREATE_NEW_CONSOLE` 都擋不住；
  `--debug 0` 也還會留下一行。所以工具先啟動一個擁有隱藏主控台的極小 Python 輔助程序，
  再由它啟動切片器並原樣傳回結束代碼，記錄就只會寫進那個看不見的主控台。
- 等待方式是有期限的輪詢，不會無限等待。逾時就用 `taskkill /F /T` 結束整個程序樹，
  並確認程序已經結束。
- **切片器有時寫完輸出後不會自行結束**（開發期間約 70 次切片中出現 2 次，程序只剩一個執行緒在等待，`taskkill` 也回報找不到執行中的執行個體）。
  `result.json` 出現後 30 秒內程序仍未結束，工具就強制結束它；只有在 `result.json` 成功、
  gcode.3mf 的 ZIP 完整時才採用結果，並在終端機顯示警告。
- 切片器會把 `result.json` 寫到目前工作目錄，所以每次切片都在自己的 `_work/<組合>/` 目錄中執行，
  結束後刪除。

## 為什麼 CLI 的 `--help` 要特別擷取

`bambu-studio.exe` 把 CLI 文字直接寫到主控台，重新導向 stdout/stderr 什麼都拿不到。
[tools/capture_console.py](../tools/capture_console.py) 會在隱藏的新主控台中執行指令，再讀取主控台緩衝區。

## 數值處理

密度清單和範圍用 `Decimal` 計算，`--range 5 6 0.1` 會得到剛好 11 個值，不會有浮點誤差造成漏掉終點。
「最少用料／最短時間」以 CSV 顯示的精度（0.01 g、1 秒）比較，並列時全部標出。
