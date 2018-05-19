# -*- mode: python -*-

block_cipher = None


AUSLAB_DIR = 'auslab'
f1_condensed = os.path.join(AUSLAB_DIR, 'F1_condensed.png')
f1_normal = os.path.join(AUSLAB_DIR, 'F1_normal.png')

a = Analysis(['main.py'],
             pathex=['G:\\workspace\\assist-main'],
             binaries=[],
             datas=[('templates.dat', '.'), (f1_condensed, AUSLAB_DIR), (f1_normal, AUSLAB_DIR)],
             hiddenimports=['PIL'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='main',
          debug=False,
          strip=False,
          upx=False,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=False,
               name='main')
