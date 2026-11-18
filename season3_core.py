"""
season3_core.py — Season 3 core module for SNIPER//NET.

Provides the install() hook expected by sniper_net-6.py (line 2246-2247).
The game imports this module at startup and calls install() with the
sniper_net-6 module object, allowing Season 3 systems to be patched in.

Most Season 3 content (weapons, ranks, rewards, profile save/load, HUD,
medkit, knife, weapon switching, UI buttons) is already inlined inside
sniper_net-6.py. This module preserves the import hook so the game can
launch, and provides a clean place for future shared Season 3 code.
"""


def install(game_module):
    """Install Season 3 core features into the game module.

    Args:
        game_module: The sniper_net-6 module (sys.modules[__name__]).
    """
    # Season 3 core installation hook.
    # Additional Season 3 systems are already inlined in sniper_net-6.py.
    # This function intentionally does no destructive patching so the game
    # launches safely. Future shared Season 3 code can be added here.
    return None
