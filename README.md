# 3 Maktab — Final (CS 1.6, Windows)

## Download and play

**[Download 3_MAKTAB_FINAL.zip](https://github.com/Fztyler/3-maktab-cs16/raw/refs/heads/main/3_MAKTAB_FINAL.zip)**

1. Extract the whole ZIP and close Counter-Strike.
2. Double-click **INSTALL.cmd** and select your CS 1.6 folder containing **hl.exe**.
3. Run **PLAY_3_MAKTAB.cmd** from your game folder. Select T or CT; bots fill 5 vs 5.

Everything required is included: BSP, textures, custom models, music, bot navigation, and Windows server support. No Blender, Python, compiler or manual console setup needed. Replaced files are backed up automatically. Use a separate CS copy if you already run a modified server.

## Установка

Скачай архив по ссылке выше → распакуй целиком → закрой CS → запусти **INSTALL.cmd** → выбери папку с **hl.exe**. Запуск: **PLAY_3_MAKTAB.cmd** в папке игры. Выбери команду; боты дополнят состав до 5 на 5.

## Map and sources

Two school buildings, gym site A, eastern toilets site B, independently breakable glass and wooden frames, usable doors, 135 trees with trunk collision, ambient radio. Latest approved version includes higher ceilings and fitted door frames. Team switch: M, once per round.

Editable source: **de_3_maktab_editor.map** (Valve220), configuration and instructions in **manual_edit/**. Generators and original Blender sketches are included. After manual compilation run **share_window_models.py**; the supplied compile script does this automatically.

The user checked the final appearance. Compilation, collision checks and fresh navigation passed; the last automated visual inspection was interrupted. Engine/build compatibility may vary. [Server component sources and licenses](SERVER_COMPONENTS.md).
