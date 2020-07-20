# -*- mode: python -*-

block_cipher = None

a = Analysis(['main.py'],
             pathex=['G:\\workspace\\assist-main', 'G:\\workspace'],
             binaries=[],
             datas=[
                ('main-grey.ico', '.'), 
                ('config.yaml', '.'), 
                ('templates-normal.dat', '.'),
                ('templates-large.dat', '.'),
                ('rc-logo.png', '.'),
                ('./darkstyle/*', 'darkstyle'),
                ('F1_normal.png', '.'), 
                ('F1_condensed.png', '.'),
                ('F1_large_normal.png', '.'),
                ('F1_large_condensed.png', '.'),
                ('ArameMono.ttf', '.'),
                ('AssistIcon.ico', '.'),
                ('version-number.txt', '.'),
             ],
             hiddenimports=['yaml', 'encodings', 'keyboard', 'peewee', 'auslab'],
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
          a.binaries,
          exclude_binaries=True,
          name='Assist',
          debug=False,
          strip=False,
          upx=False,
          icon='AssistIcon.ico',
          console=False)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=False,
               name='Assist')
