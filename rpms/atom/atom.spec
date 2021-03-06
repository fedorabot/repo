# build Atom and Electron packages: https://github.com/tensor5/arch-atom
# RPM spec: https://github.com/helber/fedora-specs
# Error: Module version mismatch. Expected 47, got 43.
# see https://github.com/tensor5/arch-atom/issues/3
%{?nodejs_find_provides_and_requires}
%global arch %(test $(rpm -E%?_arch) = x86_64 && echo "x64" || echo "ia32")
%global debug_package %{nil}
%global _hardened_build 1
%global __provides_exclude_from %{_libdir}/%{name}/node_modules
%global __requires_exclude_from %{_libdir}/%{name}/node_modules
%global __requires_exclude (npm|libnode)

%global project atom
%global repo %{project}
%global electron_ver 1.2.2
%global node_ver 0.12

# commit
%global _commit f89b273752854a1894f340a337a34bf2c6d27fc4
%global _shortcommit %(c=%{_commit}; echo ${c:0:7})

Name:    atom
Version: 1.8.0
Release: 1.git%{_shortcommit}%{?dist}
Summary: A hack-able text editor for the 21st century

Group:   Applications/Editors
License: MIT
URL:     https://atom.io/
Source0: https://github.com/atom/atom/archive/%{_commit}/%{repo}-%{_shortcommit}.tar.gz

Patch0:  fix-atom-sh.patch
Patch1:  fix-license-path.patch
Patch2:  use-system-apm.patch
Patch3:  use-system-electron.patch
# Fix for Electron 1.2.0
Patch4:  beforeunload.patch
Patch5:  run-as-node.patch
# https://github.com/tensor5/arch-atom/issues/14
Patch6:  tree-view.patch

# In fc25, the nodejs contains /bin/npm, and it do not depend node-gyp
BuildRequires: libtool
BuildRequires: npm, wget, git
BuildRequires: node-gyp
BuildRequires: nodejs-packaging
BuildRequires: nodejs-atom-package-manager
Requires: nodejs-atom-package-manager
Requires: electron
Requires: desktop-file-utils

%description
Atom is a text editor that's modern, approachable, yet hack-able to the core
- a tool you can customize to do anything but also use productively without
ever touching a config file.

Visit https://atom.io to learn more.

%prep
%setup -q -n %repo-%{_commit}
sed -i 's|<lib>|%{_lib}|g' %{P:0} %{P:3}
%patch0 -p1
%patch1 -p1
%patch2 -p1
%patch3 -p1
%patch4 -p1
%patch5 -p1

# apm with system (updated) nodejs cannot 'require' modules inside asar
sed -e "s|, 'generate-asar'||" -i build/Gruntfile.coffee

# They are known to leak data to GitHub, Google Analytics and Bugsnag.com.
sed -i -E -e '/(exception-reporting|metrics)/d' package.json

# Use settings-view@0.238.0 for Electron 1.2.0
sed -i '/setting/s|0.*"|0.238.0"|' package.json

%build
# Hardened package
export CFLAGS="%{optflags} -fPIC -pie"
export CXXFLAGS="%{optflags} -fPIC -pie"

# Update node for fc23 and el7
%if 0%{?fedora} < 24 || 0%{?rhel}
git clone https://github.com/creationix/nvm.git .nvm
source .nvm/nvm.sh
nvm install %{node_ver}
nvm use %{node_ver}
%endif

# Build package
node-gyp -v; node -v; npm -v; apm -v
## https://github.com/atom/atom/blob/master/script/bootstrap
# If unset, ~/.atom/.node-gyp/.atom/.npm is used
## https://github.com/atom/electron/blob/master/docs/tutorial/using-native-node-modules.md
npm_config_cache="${HOME}/.atom/.npm"
npm_config_disturl="https://atom.io/download/atom-shell"
npm_config_target="%{electron_ver}"
#export npm_config_target_arch="x64|ia32"
npm_config_runtime="electron"
# The npm_config_target is no effect, set ATOM_NODE_VERSION
## https://github.com/atom/apm/blob/master/src/command.coffee
export ATOM_ELECTRON_VERSION="%{electron_ver}"
export ATOM_ELECTRON_URL="$npm_config_disturl"
export ATOM_RESOURCE_PATH=`pwd`
export ATOM_HOME="$npm_config_cache"

_packagesToDedupe=(
    'abbrev'
    'amdefine'
    'atom-space-pen-views'
    'cheerio'
    'domelementtype'
    'fs-plus'
    'grim'
    'highlights'
    'humanize-plus'
    'iconv-lite'
    'inherits'
    'loophole'
    'oniguruma'
    'q'
    'request'
    'rimraf'
    'roaster'
    'season'
    'sigmund'
    'semver'
    'through'
    'temp'
)

# Fix nodegit build error for node 0.10
#https://github.com/tensor5/arch-atom/commit/afc1d1b19ba8040e3b2c1274b9f7fea426c692cd
npm install nodegit --ignore-scripts --verbose
pushd node_modules/nodegit
  npm install --ignore-scripts
  cp vendor/libssh2/win32/libssh2_config.h vendor/libssh2/include
  pushd vendor/libssh2
    autoreconf -ivf
    ./configure
  popd
  node_gyp="node_modules/.bin/node-gyp"
  $node_gyp configure rebuild --target="%{electron_ver}" --target_platform="linux" \
  --runtime="electron" --arch="%{arch}" --dist-url="$npm_config_disturl"
  echo 'Removing NodeGit devDependencies...'
  npm prune --production
popd

# Installing atom dependencies
#apm clean
apm install --verbose
apm dedupe ${_packagesToDedupe[@]}

# Installing build tools
pushd build
npm install --loglevel info
popd
script/grunt --channel=stable

# Fix height error on install page
find out -name 'settings-view.less' | xargs sed -i '/height.*100%/s|^|//|'

# Fix for Node 6
pushd node_modules/tree-view
patch -Np1 -i %{P:6}

%install
install -d %{buildroot}%{_libdir}/%{name}
cp -r out/Atom/resources/app/* %{buildroot}%{_libdir}/%{name}
rm -rf %{buildroot}%{_libdir}/%{name}/node_modules

install -d %{buildroot}%{_datadir}/applications
sed -e \
   's|<%= appName %>|Atom|
    s|<%= description %>|%{summary}|
    s|<%= installDir %>/share/<%= appFileName %>/||
    s|<%= iconPath %>|%{name}|' \
    resources/linux/atom.desktop.in > \
    %{buildroot}%{_datadir}/applications/%{name}.desktop

install -Dm0755 out/Atom/resources/new-app/atom.sh \
    %{buildroot}%{_bindir}/%{name}

# copy over icons in sizes that most desktop environments like
for i in 1024 512 256 128 64 48 32 24 16; do
    install -D -m 0644 out/icons/${i}.png \
      %{buildroot}%{_datadir}/icons/hicolor/${i}x${i}/apps/%{name}.png
done

# find all *.js files and generate node.file-list
pushd out/Atom/resources/app
for ext in js jsm json coffee map node types less png svg aff dic; do
    find node_modules -regextype posix-extended \
      -iname \*.${ext} \
    ! -name '.*' \
    ! -path '*test*' \
    ! -path '*example*' \
    ! -path '*sample*' \
    ! -path '*benchmark*' \
      -exec install -Dm644 '{}' '%{buildroot}%{_libdir}/%{name}/{}' \;
done
popd

find %{buildroot} -type f -regextype posix-extended \
    -regex '.*js$' -exec sh -c "sed -i '/^#\!\/usr\/bin\/env/d' '{}'" \; -or \
    -regex '.*node$' -type f -exec strip '{}' \; -or \
    -name '.*?' -print -or \
    -size 0 -print | xargs rm -rf

%post
/bin/touch --no-create %{_datadir}/icons/hicolor &>/dev/null ||:
/usr/bin/update-desktop-database &>/dev/null ||:

%postun
if [ $1 -eq 0 ]; then
    /bin/touch --no-create %{_datadir}/icons/hicolor &>/dev/null ||:
    /usr/bin/gtk-update-icon-cache -f -t -q %{_datadir}/icons/hicolor ||:
fi
/usr/bin/update-desktop-database &>/dev/null ||:

%posttrans
/usr/bin/gtk-update-icon-cache -f -t -q %{_datadir}/icons/hicolor ||:

%files
%defattr(-,root,root,-)
%doc README.md CONTRIBUTING.md docs/
%license LICENSE.md
%{_bindir}/%{name}
%{_libdir}/%{name}/
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/*/apps/%{name}.png

%changelog
* Thu Jun  9 2016 mosquito <sensor.wen@gmail.com> - 1.8.0-1.gitf89b273
- Release 1.8.0
- Build for electron 1.2.2
- Fix tree-view does not work
  https://github.com/FZUG/repo/issues/120
* Tue May 31 2016 mosquito <sensor.wen@gmail.com> - 1.7.4-4.git6bed3e5
- Use node-gyp@3.0.3 for el7, system node-gyp doesn't support
  the if-else conditions syntax
  See https://github.com/JCMais/node-libcurl/issues/56
* Tue May 31 2016 mosquito <sensor.wen@gmail.com> - 1.7.4-3.git6bed3e5
- Remove --build-dir option
- Update to settings-view@0.238.0
- Fix height error on install page
  https://github.com/FZUG/repo/issues/116
* Mon May 30 2016 mosquito <sensor.wen@gmail.com> - 1.7.4-2.git6bed3e5
- Fix settings-view dont work
  https://github.com/FZUG/repo/issues/114
* Thu May 26 2016 mosquito <sensor.wen@gmail.com> - 1.7.4-1.git6bed3e5
- Release 1.7.4
- Build for electron 1.2.0
- Build nodegit 0.12.2 from source code
- Add BReq libtool and git
- Update node 0.12 for fedora 23
* Thu May 26 2016 mosquito <sensor.wen@gmail.com> - 1.7.3-2.git1b3da6b
- Fix spell-check dont work
  https://github.com/FZUG/repo/issues/110
* Fri Apr 29 2016 mosquito <sensor.wen@gmail.com> - 1.7.3-1.git1b3da6b
- Release 1.7.3
- Build for electron 0.37.7
- Remove reduplicate CSP header
* Tue Apr 19 2016 mosquito <sensor.wen@gmail.com> - 1.7.2-1.git1969903
- Release 1.7.2
* Sat Apr 16 2016 mosquito <sensor.wen@gmail.com> - 1.7.1-1.git5dda304
- Release 1.7.1
* Wed Apr 13 2016 mosquito <sensor.wen@gmail.com> - 1.7.0-1.git1e7dc02
- Release 1.7.0
- Update nodegit 0.12.2 for electron 0.37.5
- Fix nodegit build error for node 0.10
* Tue Apr 12 2016 mosquito <sensor.wen@gmail.com> - 1.6.2-3.git42d7c40
- Rebuild for electron 0.37.5
* Wed Apr  6 2016 mosquito <sensor.wen@gmail.com> - 1.6.2-2.git42d7c40
- Rebuild for electron 0.37.4
- Set CSP header to allow load images
- Use ATOM_ELECTRON_URL instead of npm_config_disturl
* Sun Apr  3 2016 mosquito <sensor.wen@gmail.com> - 1.6.2-1.git42d7c40
- Release 1.6.2
* Wed Mar 30 2016 mosquito <sensor.wen@gmail.com> - 1.6.1-1.gitcd9b7d3
- Release 1.6.1
- Remove BReq nodejs, libgnome-keyring-devel, git-core
- Replace Req http-parser to desktop-file-utils
* Tue Mar 29 2016 mosquito <sensor.wen@gmail.com> - 1.6.0-3.git01c7777
- Fixes not found mime.types file
* Mon Mar 21 2016 mosquito <sensor.wen@gmail.com> - 1.6.0-2.git01c7777
- Fixes not found nodegit.node module
- Rewrite install script
* Mon Mar 21 2016 mosquito <sensor.wen@gmail.com> - 1.6.0-1.git01c7777
- Release 1.6.0
* Sun Mar 13 2016 mosquito <sensor.wen@gmail.com> - 1.5.4-3.gitb8cc0b4
- Fixes renderer path
* Sat Mar 12 2016 mosquito <sensor.wen@gmail.com> - 1.5.4-2.gitb8cc0b4
- rebuild for electron 0.36.11
* Sat Mar  5 2016 mosquito <sensor.wen@gmail.com> - 1.5.4-1.gitb8cc0b4
- Release 1.5.4
* Sun Feb 14 2016 mosquito <sensor.wen@gmail.com> - 1.5.3-2.git3e71894
- The package is split into atom, nodejs-atom-package-manager and electron
- Use system apm and electron
- Not generated asar file
- Remove exception-reporting and metrics dependencies from package.json
- Remove unnecessary files
* Sat Feb 13 2016 mosquito <sensor.wen@gmail.com> - 1.5.3-1.git3e71894
- Release 1.5.3
* Sat Feb 13 2016 mosquito <sensor.wen@gmail.com> - 1.5.2-1.git05731e3
- Release 1.5.2
* Fri Feb 12 2016 mosquito <sensor.wen@gmail.com> - 1.5.1-1.git88524b1
- Release 1.5.1
* Fri Feb  5 2016 mosquito <sensor.wen@gmail.com> - 1.4.3-1.git164201e
- Release 1.4.3
* Wed Jan 27 2016 mosquito <sensor.wen@gmail.com> - 1.4.1-2.git2cf2ccb
- Fix https://github.com/FZUG/repo/issues/64
* Tue Jan 26 2016 mosquito <sensor.wen@gmail.com> - 1.4.1-1.git2cf2ccb
- Release 1.4.1
* Sun Jan 17 2016 mosquito <sensor.wen@gmail.com> - 1.4.0-1.gite0dbf94
- Release 1.4.0
* Sun Dec 20 2015 mosquito <sensor.wen@gmail.com> - 1.3.2-1.git473e885
- Release 1.3.2
* Sat Dec 12 2015 mosquito <sensor.wen@gmail.com> - 1.3.1-1.git3937312
- Release 1.3.1
* Thu Nov 26 2015 mosquito <sensor.wen@gmail.com> - 1.2.4-1.git05ef4c0
- Release 1.2.4
* Sat Nov 21 2015 mosquito <sensor.wen@gmail.com> - 1.2.3-1.gitfb5b1ba
- Release 1.2.3
* Sat Nov 14 2015 mosquito <sensor.wen@gmail.com> - 1.2.1-1.git7e902bc
- Release 1.2.1
* Wed Nov 04 2015 mosquito <sensor.wen@gmail.com> - 1.1.0-1.git402f605
- Release 1.1.0
* Thu Sep 17 2015 Helber Maciel Guerra <helbermg@gmail.com> - 1.0.13-1
- Change lib to libnode
* Tue Sep 01 2015 Helber Maciel Guerra <helbermg@gmail.com> - 1.0.10-1
- Release 1.0.10
* Thu Aug 27 2015 Helber Maciel Guerra <helbermg@gmail.com> - 1.0.8-1
- Clean and test spec for epel, centos and fedora
- Release 1.0.8
* Tue Aug 11 2015 Helber Maciel Guerra <helbermg@gmail.com> - 1.0.6-1
- Release 1.0.6
* Thu Aug 06 2015 Helber Maciel Guerra <helbermg@gmail.com> - 1.0.5-1
- Release 1.0.5
* Wed Jul 08 2015 Helber Maciel Guerra <helbermg@gmail.com> - 1.0.1-1
- Release 1.0.1
* Thu Jun 25 2015 Helber Maciel Guerra <helbermg@gmail.com> - 1.0.0-1
- Release 1.0.0
* Wed Jun 10 2015 Helber Maciel Guerra <helbermg@gmail.com> - 0.208.0-1
- Fix atom.desktop
* Tue Jun 09 2015 Helber Maciel Guerra <helbermg@gmail.com> - 0.207.0-1
- Fix desktop icons and some rpmlint.
* Fri Oct 31 2014 Helber Maciel Guerra <helbermg@gmail.com> - 0.141.0-1
- release 0.141.0
* Thu Oct 23 2014 Helber Maciel Guerra <helbermg@gmail.com> - 0.139.0-1
- release 0.139.0
* Wed Oct 15 2014 Helber Maciel Guerra <helbermg@gmail.com> - 0.137.0-2
- release 0.137.0
* Tue Oct 07 2014 Helber Maciel Guerra <helbermg@gmail.com> - 0.136.0-1
- release 0.136.0
* Tue Sep 30 2014 Helber Maciel Guerra <helbermg@gmail.com> - 0.133.0-2
- Build OK
* Fri Aug 22 2014 Helber Maciel Guerra <helbermg@gmail.com> - 0.123.0-2
- Change package name to atom.
* Thu Aug 21 2014 Helber Maciel Guerra <helbermg@gmail.com> - 0.123.0-1
- RPM package is just working.
* Sat Jul 26 2014 Helber Maciel Guerra <helbermg@gmail.com> - 0.119.0-1
- Try without nodejs.
* Tue Jul 01 2014 Helber Maciel Guerra <helbermg@gmail.com> - 0.106.0-1
- Try new version
* Sun May 25 2014 Helber Maciel Guerra <helbermg@gmail.com> - 0.99.0
- Initial package
