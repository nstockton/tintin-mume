# -*- mode: python -*-

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import codecs
import glob
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

import PyInstaller.config
import speechlight

from mapper.utils import padList


APP_NAME = "Mapper Proxy"
APP_AUTHOR = "Nick Stockton"
VERSION_REGEX = re.compile(r"^[vV]([\d.]+)-(stable|beta)-?([\w-]*)$", re.IGNORECASE)
ORIG_DEST = os.path.realpath(os.path.expanduser(DISTPATH))  # NOQA: F821
isTag = False
found_version = None
for arg in sys.argv[1:]:
	match = VERSION_REGEX.search(arg.strip().lower())
	if match is not None:
		APP_VERSION = match.groups()[0]
		if match.groups()[2].startswith("0-g"):
			APP_VERSION_TYPE = match.groups()[1]
			isTag = True
		else:
			APP_VERSION_TYPE = "_".join(match.groups()[1:])
		found_version = "command line"
		break
else:
	if (
		os.path.exists(os.path.normpath(os.path.join(ORIG_DEST, os.pardir, "version.ignore")))
		and not os.path.isdir(os.path.normpath(os.path.join(ORIG_DEST, os.pardir, "version.ignore")))
	):
		with codecs.open(
			os.path.normpath(os.path.join(ORIG_DEST, os.pardir, "version.ignore")),
			"rb",
			encoding="utf-8"
		) as f:
			match = VERSION_REGEX.search(f.read(30).strip().lower())
			if match is not None:
				APP_VERSION = match.groups()[0]
				if match.groups()[2].startswith("0-g"):
					APP_VERSION_TYPE = match.groups()[1]
					isTag = True
				else:
					APP_VERSION_TYPE = "_".join(match.groups()[1:])
				found_version = "version file"
	elif (
		os.path.exists(os.path.normpath(os.path.join(ORIG_DEST, os.pardir, ".git")))
		and os.path.isdir(os.path.normpath(os.path.join(ORIG_DEST, os.pardir, ".git")))
	):
		try:
			match = VERSION_REGEX.search(
				subprocess.check_output(
					"git describe --tags --always --long",
					shell=True
				).decode("utf-8").strip().lower()
			)
			if match is not None:
				APP_VERSION = match.groups()[0]
				if match.groups()[2].startswith("0-g"):
					APP_VERSION_TYPE = match.groups()[1]
					isTag = True
				else:
					APP_VERSION_TYPE = "_".join(match.groups()[1:])
				found_version = "latest Git tag"
		except subprocess.CalledProcessError:
			pass
if found_version:
	print("Using version info from {}. ({}-{})".format(found_version, APP_VERSION, APP_VERSION_TYPE))
else:
	APP_VERSION = "0.0"
	APP_VERSION_TYPE = "beta"
	print("No version information found. Using default. ({}-{})".format(APP_VERSION, APP_VERSION_TYPE))
# APP_VERSION_CSV should be a string containing a comma separated list of numbers in the version.
# For example, "17, 4, 5, 0" if the version is 17.4.5.
APP_VERSION_CSV = ", ".join(padList(APP_VERSION.split("."), padding="0", count=4, fixed=True))
APP_DEST = os.path.normpath(
	os.path.join(
		ORIG_DEST,
		os.pardir,
		"{}_V{}_{}".format(APP_NAME, APP_VERSION, APP_VERSION_TYPE).replace("-", "_").replace(" ", "_")
	)
)
if isTag:
	ZIP_FILE = APP_DEST + ".zip"
else:
	ZIP_FILE = os.path.normpath(os.path.join(ORIG_DEST, os.pardir, "MapperProxy.zip"))
VERSION_FILE = os.path.normpath(
	os.path.join(os.path.realpath(os.path.expanduser(tempfile.gettempdir())), "mpm_version.ignore")
)
PyInstaller.config.CONF["distpath"] = APP_DEST

excludes = [
	"_gtkagg",
	"_tkagg",
	"bsddb",
	"curses",
	"pywin.debugger",
	"pywin.debugger.dbgcon",
	"pywin.dialogs",
	"tcl",
	"Tkconstants",
	"tkinter.constants",
	"Tkinter",
	"tkinter",
	"multiprocessing",
	"bz2",
	"lzma",
	"_testcapi",
	"pdbunittest",
	"difflib",
	"pyreadline",
	"optparse",
	"numpy",
	"PIL",
	"xml"
]

dll_excludes = TOC([  # NOQA: F821
	("api-ms-win-core-console-l1-1-0.dll", None, None),
	("api-ms-win-core-datetime-l1-1-0.dll", None, None),
	("api-ms-win-core-debug-l1-1-0.dll", None, None),
	("api-ms-win-core-errorhandling-l1-1-0.dll", None, None),
	("api-ms-win-core-file-l1-1-0.dll", None, None),
	("api-ms-win-core-file-l1-2-0.dll", None, None),
	("api-ms-win-core-file-l2-1-0.dll", None, None),
	("api-ms-win-core-handle-l1-1-0.dll", None, None),
	("api-ms-win-core-heap-l1-1-0.dll", None, None),
	("api-ms-win-core-interlocked-l1-1-0.dll", None, None),
	("api-ms-win-core-libraryloader-l1-1-0.dll", None, None),
	("api-ms-win-core-localization-l1-2-0.dll", None, None),
	("api-ms-win-core-memory-l1-1-0.dll", None, None),
	("api-ms-win-core-namedpipe-l1-1-0.dll", None, None),
	("api-ms-win-core-processenvironment-l1-1-0.dll", None, None),
	("api-ms-win-core-processthreads-l1-1-0.dll", None, None),
	("api-ms-win-core-processthreads-l1-1-1.dll", None, None),
	("api-ms-win-core-profile-l1-1-0.dll", None, None),
	("api-ms-win-core-rtlsupport-l1-1-0.dll", None, None),
	("api-ms-win-core-string-l1-1-0.dll", None, None),
	("api-ms-win-core-synch-l1-1-0.dll", None, None),
	("api-ms-win-core-synch-l1-2-0.dll", None, None),
	("api-ms-win-core-sysinfo-l1-1-0.dll", None, None),
	("api-ms-win-core-timezone-l1-1-0.dll", None, None),
	("api-ms-win-core-util-l1-1-0.dll", None, None),
	("api-ms-win-crt-conio-l1-1-0.dll", None, None),
	("api-ms-win-crt-convert-l1-1-0.dll", None, None),
	("api-ms-win-crt-environment-l1-1-0.dll", None, None),
	("api-ms-win-crt-filesystem-l1-1-0.dll", None, None),
	("api-ms-win-crt-heap-l1-1-0.dll", None, None),
	("api-ms-win-crt-locale-l1-1-0.dll", None, None),
	("api-ms-win-crt-math-l1-1-0.dll", None, None),
	("api-ms-win-crt-multibyte-l1-1-0.dll", None, None),
	("api-ms-win-crt-process-l1-1-0.dll", None, None),
	("api-ms-win-crt-runtime-l1-1-0.dll", None, None),
	("api-ms-win-crt-stdio-l1-1-0.dll", None, None),
	("api-ms-win-crt-string-l1-1-0.dll", None, None),
	("api-ms-win-crt-time-l1-1-0.dll", None, None),
	("api-ms-win-crt-utility-l1-1-0.dll", None, None),
	("tcl86t.dll", None, None),
	("tk86t.dll", None, None),
	("ucrtbase.dll", None, None),
	("mfc140u.dll", None, None)
])

block_cipher = None

version_data = """
# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set not needed items to zero 0.
    filevers=({version_csv}),
    prodvers=(1, 0, 0, 1),
    # Contains a bitmask that specifies the valid bits 'flags'r
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - NT and there is no need to change it.
    OS=0x40004,
    # The general type of file.
    # 0x1 - the file is an application.
    fileType=0x1,
    # The function of the file.
    # 0x0 - the function is not defined for this fileType
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'LFileDescript'),
        StringStruct(u'', u'{name} V{version}-{version_type}'),
        StringStruct(u'FileVersion', u'{version}'),
        StringStruct(u'LegalCopyright', u'{author}'),
        StringStruct(u'OriginalFilename', u'{name}.exe'),
        StringStruct(u'ProductName', u'{name}'),
        StringStruct(u'ProductVersion', u'{version}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
""".format(
	name=APP_NAME,
	version=APP_VERSION,
	version_type=APP_VERSION_TYPE,
	version_csv=APP_VERSION_CSV,
	author=APP_AUTHOR
)

# Remove old dist directory and old version file.
shutil.rmtree(ORIG_DEST, ignore_errors=True)
shutil.rmtree(APP_DEST, ignore_errors=True)
if os.path.exists(ZIP_FILE) and not os.path.isdir(ZIP_FILE):
	os.remove(ZIP_FILE)
if (
	os.path.exists(os.path.normpath(os.path.join(APP_DEST, os.pardir, "mpm_version.py")))
	and not os.path.isdir(os.path.normpath(os.path.join(APP_DEST, os.pardir, "mpm_version.py")))
):
	os.remove(os.path.normpath(os.path.join(APP_DEST, os.pardir, "mpm_version.py")))
shutil.rmtree(VERSION_FILE, ignore_errors=True)

with codecs.open(VERSION_FILE, "wb", encoding="utf-8") as f:
	f.write(version_data)

with codecs.open(
	os.path.normpath(os.path.join(APP_DEST, os.pardir, "mpm_version.py")),
	"wb",
	encoding="utf-8"
) as f:
	f.write("version = \"{} V{}-{}\"".format(APP_NAME, APP_VERSION, APP_VERSION_TYPE))

a = Analysis(  # NOQA: F821
	["start.py"],
	pathex=[os.path.normpath(os.path.join(APP_DEST, os.pardir))],
	binaries=[],
	datas=[],
	hiddenimports=["uuid"],
	hookspath=[],
	runtime_hooks=[],
	excludes=excludes,
	win_no_prefer_redirects=False,
	win_private_assemblies=False,
	cipher=block_cipher,
	noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # NOQA: F821

exe = EXE(  # NOQA: F821
	pyz,
	a.scripts,
	[],
	exclude_binaries=True,
	name=APP_NAME,
	debug=False,
	bootloader_ignore_signals=False,
	strip=False,
	upx=False,  # Not using UPX for the moment, as it can raise false positives in some antivirus software.
	runtime_tmpdir=None,
	console=True,
	version=VERSION_FILE
)

coll = COLLECT(  # NOQA: F821
	exe,
	a.binaries - dll_excludes,
	a.zipfiles,
	a.datas,
	strip=False,
	upx=False,
	name=""
)

# Remove junk.
shutil.rmtree(ORIG_DEST, ignore_errors=True)
shutil.rmtree(os.path.normpath(os.path.join(APP_DEST, os.pardir, "__pycache__")), ignore_errors=True)
shutil.rmtree(os.path.realpath(os.path.expanduser(workpath)), ignore_errors=True)  # NOQA: F821
# The directory above workpath should now be empty.
# Using os.rmdir to remove it instead of shutil.rmtree for safety.
os.rmdir(
	os.path.normpath(os.path.join(os.path.realpath(os.path.expanduser(workpath)), os.pardir))  # NOQA: F821
)
if (
	os.path.exists(os.path.normpath(os.path.join(APP_DEST, os.pardir, "mpm_version.py")))
	and not os.path.isdir(os.path.normpath(os.path.join(APP_DEST, os.pardir, "mpm_version.py")))
):
	os.remove(os.path.normpath(os.path.join(APP_DEST, os.pardir, "mpm_version.py")))
shutil.rmtree(os.path.join(APP_DEST, "Include"), ignore_errors=True)
shutil.rmtree(os.path.join(APP_DEST, "lib2to3", "tests"), ignore_errors=True)

lib_files = []

for files, destination in lib_files:
	dest_dir = os.path.join(APP_DEST, destination)
	if not os.path.exists(dest_dir):
		os.makedirs(dest_dir)
	for src in files:
		if os.path.exists(src) and not os.path.isdir(src):
			shutil.move(src, dest_dir)

include_files = [
	(
		[
			os.path.normpath(os.path.join(APP_DEST, os.pardir, "LICENSE.txt")),
			os.path.normpath(os.path.join(APP_DEST, os.pardir, "README.md"))
		],
		"."
	),
	(
		glob.glob(os.path.join(os.path.realpath(os.path.expanduser(speechlight.where())), "*.dll")),
		"speech_libs"
	),
	(glob.glob(os.path.normpath(os.path.join(APP_DEST, os.pardir, "maps", "*.sample"))), "maps"),
	(glob.glob(os.path.normpath(os.path.join(APP_DEST, os.pardir, "data", "*.sample"))), "data"),
	(glob.glob(os.path.normpath(os.path.join(APP_DEST, os.pardir, "tiles", "*"))), "tiles")
]

for files, destination in include_files:
	dest_dir = os.path.join(APP_DEST, destination)
	if not os.path.exists(dest_dir):
		os.makedirs(dest_dir)
	for src in files:
		if os.path.exists(src) and not os.path.isdir(src):
			shutil.copy(src, dest_dir)

print("Compressing the distribution to {}.".format(ZIP_FILE))
shutil.make_archive(
	base_name=os.path.splitext(ZIP_FILE)[0],
	format="zip",
	root_dir=os.path.normpath(os.path.join(APP_DEST, os.pardir)),
	base_dir=os.path.basename(APP_DEST),
	owner=None,
	group=None
)
shutil.rmtree(APP_DEST, ignore_errors=True)

print("Generating checksums.")
hashes = {
	"sha256": hashlib.sha256()
}
block_size = 2 ** 16
with open(ZIP_FILE, "rb") as f:
	for block in iter(lambda: f.read(block_size), b""):
		for _, hash in hashes.items():
			hash.update(block)
for hashtype, hash in hashes.items():
	with codecs.open("{}.{}".format(ZIP_FILE, hashtype), "wb", encoding="utf-8") as f:
		f.write("{} *{}\n".format(hash.hexdigest().lower(), os.path.basename(ZIP_FILE)))

print("Done.")
