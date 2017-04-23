#!/usr/bin/python3.5
import argparse
import logging
import pathlib
import re
import sys
import unittest


# Requires python >= 3.5 because of newer pathlib API.


class PortageAtom:
    def __init__(self, atom_str: str = None):
        self.condition = ''
        self.category = ''
        self.package = ''
        self.version = ''
        self.slot = ''
        self.repo = ''
        self.parameters = ''
        self.parse_from_str(atom_str)

    def is_invalid(self) -> bool:
        return (self.category == '') and (self.package == '')

    def __str__(self):
        if self.is_invalid():
            return '<Invalid atom>'
        s = '{}/{}'.format(self.category, self.package)
        if self.version != '':
            s += ('-' + self.version)
        return s

    def get_full_str(self) -> str:
        if self.is_invalid(): return ''
        s = self.condition
        s += self.category + '/' + self.package
        if self.version != '':
            s += '-' + self.version
        if self.slot != '':
            s += ':' + self.slot
        if self.repo != '':
            s += '::' + self.repo
        if self.parameters != '':
            s += ' ' + self.parameters
        return s

    def parse_from_str(self, atom_str: str):
        if atom_str is None:
            return

        atom_str = atom_str.strip()
        if atom_str.startswith('#'):
            # comments shall not pass
            return

        # split parameters
        self.parameters = ''
        parts = atom_str.split(' ', 1)
        if len(parts) == 2:
            atom_str = parts[0].strip()
            self.parameters = parts[1].strip()

        # get condition
        if atom_str.startswith('<='):
            self.condition = '<='
        elif atom_str.startswith('>='):
            self.condition = '>='
        elif atom_str.startswith('>'):
            self.condition = '>'
        elif atom_str.startswith('<'):
            self.condition = '<'
        elif atom_str.startswith('='):
            self.condition = '='
        else:
            self.condition = ''  # empty condition is allowed

        clen = len(self.condition)
        if clen > 0:
            atom_str = atom_str[clen:]

        # it may contain repo part "::gentoo"
        self.repo = ''
        spos = atom_str.find('::')
        if spos > 0:
            self.repo = atom_str[spos + 2:]
            atom_str = atom_str[:spos]
            # print('    after split: {}, repoo={}'.format(atom_str, self.repo))
            # after split: dev-qt/designer-5.7.1:5/5.7, repoo=gentoo

        # split category
        parts = atom_str.split('/', 1)
        self.category = parts[0]
        atom_str = parts[1]
        # print('After category split: atom_str={}, category={}'.format(atom_str, self.category))
        # After category split: atom_str=designer-5.7.1:5/5.7, category=dev-qt

        # we should split possible slot already here, before version parsing
        self.slot = ''
        spos = atom_str.find(':')
        if spos > 0:
            parts = atom_str.split(':', 1)
            atom_str = parts[0]
            self.slot = parts[1]

        # the most hard part - split version
        parts = atom_str.split('-')

        self.package = ''
        self.version = ''

        # regular expression that version part should match
        r = re.compile(r'[0-9\.r]')

        for p in parts:
            m = r.match(p)
            if m is not None:
                if self.version != '':
                    self.version += '-'
                self.version += p
            else:
                if self.package != '':
                    self.package += '-'
                self.package += p


class KeeperConfig:
    def __init__(self):
        self.PORTAGE_ETC_DIR = '/etc/portage'
        self.OUTPUT_DIR = './keeper_out'


class Keeper:
    def __init__(self):
        self.config = KeeperConfig()
        self.action = ''
        self._debug = False

    def parse_args(self):
        ap = argparse.ArgumentParser(description="Keeps /etc/portage/{package.accept_keywords,"
                                     "package.use, package.mask,package.unmask} in order: "
                                     "each package should be in file named accordingly to its "
                                     "category, sorted there alphabetically. For example: all "
                                     "dev-python/* packages should be mentioned only in files "
                                     "'/etc/portage/package.accept_keywords/dev-python' or "
                                     "'/etc/portage/package.use/dev-python'. Requires python "
                                     ">= 3.5 to run!"
                                     )
        ap.add_argument('--portage_etc_dir', action='store', nargs='?', type=str, default='/etc/portage',
                        required=False, help='Location of portage configuration, default: /etc/portage')
        ap.add_argument('--outdir', action='store', nargs='?', type=str, default='./keeper_out',
                        required=False, help="Where to put result files for action 'sort'")
        ap.add_argument('--debug', action='store_true', help='Enable more debug output')
        ap.add_argument('action', action='store', nargs=1, metavar='action',
                        choices=['sort', 'verify', 'mask', 'unmask', 'unkeyword'],
                        help="Action to perform. Possible actions:"
                        " 'sort': scan all files in portage dir and bring them to order. "
                        " 'verify': check that package versions mentioned really exist. "
                        )
        args = ap.parse_args()
        # print(args)

        self.config.PORTAGE_ETC_DIR = args.portage_etc_dir
        self.config.OUTPUT_DIR = args.outdir
        self._debug = args.debug
        if args.action is not None:
            self.action = args.action[0]

        self.init_logging()

    def init_logging(self):
        self.log = logging.getLogger('Keeper')
        self.log.setLevel(logging.DEBUG)
        ch = logging.StreamHandler(stream=sys.stdout)
        if self._debug:
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(levelname)s [%(funcName)s:%(lineno)d] %(message)s')
        else:
            ch.setLevel(logging.INFO)
            formatter = logging.Formatter('%(levelname)s %(message)s')
        ch.setFormatter(formatter)
        self.log.addHandler(ch)

    @staticmethod
    def error_exit(comment: str):
        print(comment, file=sys.stderr)
        sys.exit(1)

    def run(self):
        self.parse_args()
        if (self.action is None) or (self.action == ''):
            self.error_exit('"action" should be specified. See {} --help\n'.format(sys.argv[0]))
        if self.action == 'sort':
            self.run_sort()
        else:
            self.error_exit("Action '{}' is not implemented.".format(self.action))

    def run_sort(self):
        self.log.info('Will put resulting files to: {}'.format(self.config.OUTPUT_DIR))
        p = pathlib.Path(self.config.PORTAGE_ETC_DIR)
        self.run_sort_directory(p.joinpath('package.accept_keywords'))
        self.run_sort_directory(p.joinpath('package.use'))
        self.run_sort_directory(p.joinpath('package.mask'))
        self.run_sort_directory(p.joinpath('package.unmask'))

    def run_sort_directory(self, dirname: pathlib.Path):
        if not dirname.is_dir():
            self.log.error('Cannot open directory: {}'.format(dirname.as_posix()))
            return

        category_dict = {}

        self.log.info('Processing dir: {}'.format(dirname.as_posix()))
        filelist = sorted(dirname.glob('*'))
        for filepath in filelist:
            if filepath.is_symlink():
                self.log.debug('  Skipped symlink: {}'.format(filepath.as_posix()))
                continue
            self.log.debug('  Reading: {}'.format(filepath.as_posix()))
            try:
                with open(filepath.as_posix(), mode='rt', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line == '': continue
                        if line[0] == '#': continue
                        patom = PortageAtom(line)
                        if patom.is_invalid():
                            # invalid atom or parse error
                            self.log.error('Failed to parse line: [{}] as package atom.'.format(line))
                        else:
                            if not patom.category in category_dict.keys():
                                category_dict[patom.category] = []
                            category_dict[patom.category].append(patom)
            except IOError:
                self.log.exception('I/O error reading {}'.format(filepath.as_posix()))

        # make sure output directory exists
        last_part = dirname.parts[len(dirname.parts) -1]
        outdir = pathlib.Path(self.config.OUTPUT_DIR)
        if not outdir.exists():
            outdir.mkdir(parents=True, exist_ok=True)
        outdir = outdir.joinpath(last_part)
        if not outdir.exists():
            outdir.mkdir(parents=True, exist_ok=True)

        # output:
        ckeys = sorted(category_dict.keys())
        for cat in ckeys:
            outfile = outdir.joinpath(cat)
            self.log.debug('  Writing {}...'.format(outfile.as_posix()))
            try:
                with open(outfile.as_posix(), mode='wt', encoding='utf-8') as fo:
                    palist = sorted(category_dict[cat], key=lambda x: str(x).lower())
                    for patom in palist:
                        fo.write(patom.get_full_str() + '\n')
            except IOError:
                self.log.exception('Failed to write output file: {}'.format(outfile.as_posix()))


class PortageAtomTest(unittest.TestCase):
    def setUp(self):
        self.atoms = [
            '=dev-util/cmake-3.6.2 ~amd64',
            '=dev-python/ssl-fetch-0.4 ~amd64',
            '=dev-libs/double-conversion-2.0.1 ~amd64',
            'kde-apps/dolphin',
            '<=kde-apps/libkonq-15.12.2 ~amd64',
            '#=kde-apps/libkonq-9999 **',
            '<=x11-drivers/xf86-video-virtualbox-5.1.20 ~amd64',
            '>=mail-client/trojita-0.7-r2 **',
            '>category/package-0.7-r2 **',
            # USE flags
            'media-libs/mesa xa gles2',
            'media-video/vlc -qt4 qt5 vdpau theora speex taglib skins mtp lua egl directfb bluray alsa',
            '>=dev-qt/qtwayland-5.6.2 egl',
            'dev-libs/json-glib abi_x86_32',
            'kde-apps/libkipi:4 minimal',
            # synthetic test for repo
            '<=x11-drivers/xf86-video-virtualbox-5.1.20::gentoo ~amd64',
            '=dev-qt/designer-5.7.1:5/5.7::gentoo  declarative -debug -test -webkit',
        ]
        self.conditions = [
            '=',
            '=',
            '=',
            '',
            '<=',
            '',
            '<=',
            '>=',
            '>',
            # USE flags
            '',
            '',
            '>=',
            '',
            '',
            # repo
            '<=',
            '=',
        ]
        self.categories = [
            'dev-util',
            'dev-python',
            'dev-libs',
            'kde-apps',
            'kde-apps',
            '',
            'x11-drivers',
            'mail-client',
            'category',
            # USE flags
            'media-libs',
            'media-video',
            'dev-qt',
            'dev-libs',
            'kde-apps',
            # repo
            'x11-drivers',
            'dev-qt',
        ]
        self.packages = [
            'cmake',
            'ssl-fetch',
            'double-conversion',
            'dolphin',
            'libkonq',
            '',
            'xf86-video-virtualbox',
            'trojita',
            'package',
            # USE flags
            'mesa',
            'vlc',
            'qtwayland',
            'json-glib',
            'libkipi',
            # repo
            'xf86-video-virtualbox',
            'designer',
        ]
        self.versions = [
            '3.6.2',
            '0.4',
            '2.0.1',
            '',
            '15.12.2',
            '',
            '5.1.20',
            '0.7-r2',
            '0.7-r2',
            # USE flags
            '',
            '',
            '5.6.2',
            '',
            '',
            # repo
            '5.1.20',
            '5.7.1',
        ]
        self.slots = [
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            # USE flags
            '',
            '',
            '',
            '',
            '4',
            # repo
            '',
            '5/5.7',
        ]
        self.repos = [
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            # USE flags
            '',
            '',
            '',
            '',
            '',
            # repo
            'gentoo',
            'gentoo',
        ]
        self.parameters = [
            '~amd64',
            '~amd64',
            '~amd64',
            '',
            '~amd64',
            '',
            '~amd64',
            '**',
            '**',
            # USE flags
            'xa gles2',
            '-qt4 qt5 vdpau theora speex taglib skins mtp lua egl directfb bluray alsa',
            'egl',
            'abi_x86_32',
            'minimal',
            # repos
            '~amd64',
            'declarative -debug -test -webkit',
        ]

    def test_parseCondition(self):
        i = 0
        for atom in self.atoms:
            p = PortageAtom(atom)
            self.assertEqual(p.condition, self.conditions[i], atom)
            i += 1

    def test_parseParams(self):
        i = 0
        for atom in self.atoms:
            p = PortageAtom(atom)
            self.assertEqual(p.parameters, self.parameters[i], atom)
            i += 1

    def test_parseCategories(self):
        i = 0
        for atom in self.atoms:
            p = PortageAtom(atom)
            self.assertEqual(p.category, self.categories[i], atom)
            i += 1

    def test_parsePackages(self):
        i = 0
        for atom in self.atoms:
            p = PortageAtom(atom)
            self.assertEqual(p.package, self.packages[i], atom)
            i += 1

    def test_parseVersions(self):
        i = 0
        for atom in self.atoms:
            p = PortageAtom(atom)
            self.assertEqual(p.version, self.versions[i], atom)
            i += 1

    def test_parseSlots(self):
        i = 0
        for atom in self.atoms:
            p = PortageAtom(atom)
            self.assertEqual(p.slot, self.slots[i], atom)
            i += 1

    def test_parseRepos(self):
        i = 0
        for atom in self.atoms:
            p = PortageAtom(atom)
            self.assertEqual(p.repo, self.repos[i], atom)
            i += 1


def main():
    keeper = Keeper()
    keeper.run()


if __name__ == '__main__':
    main()
