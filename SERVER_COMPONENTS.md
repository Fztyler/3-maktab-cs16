# Server components in the optional Windows archive

The archive contains unmodified upstream runtime binaries, their bundled files,
and the map-specific `maktab_penetration.sma` plugin with its compiled `.amxx`.
The following upstream repositories provide the corresponding source and licenses:

- Metamod-R 1.3.0.149: https://github.com/rehlds/Metamod-R/tree/1.3.0.149
- AMX Mod X 1.10.0.5474: https://github.com/alliedmodders/amxmodx (1.10 development branch; build 5474).
- ReAPI 5.29.0.358: https://github.com/rehlds/ReAPI/tree/5.29.0.358
- ReGameDLL_CS 5.30.0.814: https://github.com/rehlds/ReGameDLL_CS/tree/5.30.0.814

The map's wall-count rule runs only on `de_3_maktab`. It changes penetration
counts and bullet exit distance, including shotgun pellets. Weapon damage,
fire rate and spread are preserved. Engine thickness/angle checks and damage
loss still apply. The BSP alone cannot enforce these server rules.

The installation routes Metamod to `addons/maktab/regamedll.dll` and enables
bots through `game_init.cfg`. Existing server administrators should merge
configuration changes rather than replace their server configuration.
