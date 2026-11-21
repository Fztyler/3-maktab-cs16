#include <amxmodx>
#include <reapi>

#define GRENADE_CARRY_LIMIT 4

// This native is exported by the installed ReAPI module, whose local include predates it.
native rg_set_global_iteminfo(const {WeaponIdType, _}:weapon_id, ItemInfo:type, any:...);

new const WeaponIdType:GRENADE_TYPES[] = {
    WEAPON_HEGRENADE, WEAPON_FLASHBANG, WEAPON_SMOKEGRENADE
};

public plugin_init()
{
    register_plugin("WW2 grenade carry limit", "1.0", "Insomnia project");

    for (new i = 0; i < sizeof GRENADE_TYPES; i++)
    {
        new WeaponIdType:grenade = GRENADE_TYPES[i];
        rg_set_weapon_info(grenade, WI_MAX_ROUNDS, GRENADE_CARRY_LIMIT);
        rg_set_global_iteminfo(grenade, ItemInfo_iMaxAmmo1, GRENADE_CARRY_LIMIT);
    }
}
