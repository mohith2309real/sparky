"""Build Finder layout metadata directly, without scripting the Finder UI."""
from pathlib import Path
import dmgbuild
ROOT=Path(__file__).resolve().parents[1]
dmgbuild.build_dmg(str(ROOT/'dist/Sparky-Installer.dmg'),'Sparky',settings={
    'format':'UDZO','compression_level':9,
    'files':[str(ROOT/'dist/Sparky.app')], 'symlinks':{'Applications':'/Applications'},
    'background':str(ROOT/'assets/dmg-background.png'),
    'icon':str(ROOT/'assets/sparky.icns'),
    'window_rect':((140,140),(640,420)), 'icon_size':96,'text_size':14,
    'icon_locations':{'Sparky.app':(170,230),'Applications':(470,230)},
    'hide_extensions':['Sparky.app'], 'default_view':'icon-view',
})
print('Created branded Sparky DMG.')
