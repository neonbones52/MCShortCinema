# Инструменты: проверенное состояние (2026-11-16)

| Что | Состояние |
|---|---|
| Blender | **5.2.2 LTS**, `D:\Apps\Blender` |
| Видеокарта | GTX 1660 6GB, драйвер 616.92, CUDA и OptiX работают |
| MCprep | **3.6.3**, включён. Риги грузятся в 5.2: зомби-житель, житель, лошадь, игрок с бронёй (iron, netherite и др.) |
| Аддон BlenderMCP в Blender | **v2.0, протокол 16, совпадает с сервером** (обновлён 2026-11-16, старый сохранён как `blender_mcp.py.bak`). Порт 9876 |
| Запись в Claude Desktop | установщик добавил `blender` (uvx mcp-for-blender) в `claude_desktop_config.json`. Это для вкладки Chat; вкладка Code использует `.mcp.json` проекта |
| MCP-сервер | `mcp-for-blender` 2.3.0 в `.venv-blender-mcp\`, подключён через `.mcp.json`. Через uvx не ставится: антивирус блокирует pywin32 |
| Телеметрия MCP | **выключена** (`telemetry_consent: false`; в новых версиях она включается только по согласию) |
| Mineways | **14.02**, `C:\Games\mineways` (есть папка `scripting`, то есть экспорт можно автоматизировать) |
| Minecraft | 26.2 Fabric (TLauncher): Litematica, WorldEdit, Sodium, Lithium, Distant Horizons |
| MCBuilder | `C:\Games\MCBuilder`: сцена на Python → `.litematic` |

## Инструменты MCP, которые у меня будут
- `execute_blender_code`: любой Python в твоём Blender. Основной инструмент.
- `get_scene_info`: что есть в сцене, где и какого размера.
- `look`: картинка сцены, так я «вижу» результат.
- `get_addon_status`: проверка связи и версий.
- `search_assets` / `import_asset`: Poly Haven и т. п. (сейчас выключено; для ванили не нужно).
- `generate_3d` / `generate_gaussian_world`: ИИ-генерация моделей и миров (нам не нужно).
- `disable_telemetry`, `record_trajectory_feedback`: служебные.

## Обновление аддона (по желанию, решает пользователь)
Перед обновлением сделать резервную копию `blender_mcp.py` из папки аддонов Blender.
Команда: `.venv-blender-mcp\Scripts\mcp-for-blender.exe install-addon`, затем перезапустить Blender и нажать Start MCP Server в панели BlenderMCP.

## Как блоки попадают в Blender (проверено 2026-11-16, Minecraft не нужен)
1. Скрипт локации `sets\<имя>.py` (на mcvox из MCBuilder) → `assets\sets\<имя>.schem` (Sponge v3, `tools\schem.py`).
2. Mineways без окна открывает `.schem` и выгружает OBJ с текстурами 26.2 → `assets\sets\obj\`.
   Одна команда: `python tools\build_set.py <имя>`.
   Атлас текстур `assets\mineways\terrainExt_26_2.png` собран TileMaker'ом из джарника 26.2.
3. Blender: импорт OBJ (forward −Z, up Y) → MCprep `prep_materials` с `animateTextures=False`.
   Иначе MCprep подменяет воду, листву, фонари и стекло текстурами из своего старого пакета, причём листва остаётся без цвета биома.
4. Анимацию воды, огня и фонарей сделаем своими средствами из кадров 26.2, когда понадобится.

Litematica остаётся для того, чтобы посмотреть локацию в игре, если захочется.
