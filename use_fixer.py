#!/usr/bin/python3
import argparse
import pathlib  # Python >= 3.5
import sys


g_new_files = []
g_modified_files = []


def add_modified_file(fn: str) -> None:
    global g_modified_files
    if fn not in g_modified_files:
        g_modified_files.append(fn)


def add_new_file(fn: str) -> None:
    global g_new_files
    if fn not in g_new_files:
        g_new_files.append(fn)


def get_existing_useflags(in_file: pathlib.Path, pn: str) -> list:
    ret = []
    try:
        with open(str(in_file), mode='rt', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if len(line) < 1:
                    continue
                if line[0] == '#':
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                line_pn = parts[0]
                if line_pn == pn:
                    for i in range(1, len(parts)):
                        ret.append(parts[i])
            f.close()
    except IOError:
        pass
    return ret


def file_write_lines(out_file: pathlib.Path, lines: list) -> bool:
    try:
        with open(str(out_file), mode='wt', encoding='utf-8') as f:
            # f.writelines(existing_lines) # does not add '\n's
            for line in lines:
                f.write(line)
                f.write('\n')
            f.close()
    except IOError:
        print('ERROR: Failed to write file: {}\n'.format(str(out_file)), file=sys.stderr)
        return False
    return True


def write_useflags(out_dir: pathlib.Path,
                   category: str,
                   package: str,
                   useflags: list,
                   no_overwrite_mode: bool = False) -> None:
    global g_new_files
    global g_modified_files

    out_file = out_dir / category
    out_file2 = out_dir / ("._cfg0000_" + category)

    # destination file may exist; read/save its contents first
    existing_lines = []
    if out_file.exists():
        with open(str(out_file), mode='rt', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if len(line) < 1:  # skip empty lines
                    continue
                if line[0] == '#':  # skip comments
                    continue
                existing_lines.append(line)
            f.close()
        if no_overwrite_mode:
            # Do not overwite file, create a new file with ".new" suffix instead
            out_file = out_dir / (category + '.new')
            add_new_file(str(out_file))
        else:
            add_modified_file(str(out_file))
    else:
        add_new_file(str(out_file))

    # existing_lines contain lines in the following format:
    #  <category/package> <use flags separated by spaces ...>
    package_name = '{}/{}'.format(category, package)
    new_line = '{} {}'.format(package_name, ' '.join(useflags))

    # find package line in existing lines
    found = False
    for i in range(len(existing_lines)):
        if existing_lines[i].startswith(package_name):
            found = True
            existing_lines[i] = new_line
            break
    if not found:
        existing_lines.append(new_line)

    # sort them
    existing_lines = sorted(existing_lines)

    # finally write them
    file_write_lines(out_file, existing_lines)
    file_write_lines(out_file2, existing_lines)


def add_useflag(in_dir: pathlib.Path, out_dir: pathlib.Path, pn: str, useflag: str) -> None:
    no_overwrite_mode = str(in_dir) == str(out_dir)
    parts = pn.split('/')
    if len(parts) < 2:
        raise RuntimeError("Wrong pn: " + str(pn))

    category = parts[0]
    package = parts[1]
    in_file = in_dir / category

    existing_use = get_existing_useflags(in_file, pn)
    if useflag not in existing_use:
        existing_use.append(useflag)

    newuse = sorted(existing_use)
    write_useflags(out_dir, category, package, newuse, no_overwrite_mode)


def main():

    ap = argparse.ArgumentParser(
                    description='Reads USE flags from onle file and applies '
                                'them to files split properly by categories.')
    ap.add_argument('--in-dir',
                    action='store',
                    nargs='?',
                    type=str,
                    default='/etc/portage/package.use',
                    required=True,
                    help='Directory where existing files with use flags are')
    ap.add_argument('--out-dir',
                    action='store',
                    nargs='?',
                    type=str,
                    default=None,
                    help='Directory where to put resulting files (optional)')
    ap.add_argument('--in-file',
                    action='store',
                    nargs='?',
                    type=str,
                    required=True,
                    help='File with input use flags')
    args = ap.parse_args()

    if args.out_dir is None:
        args.out_dir = args.in_dir

    in_dir = pathlib.Path(args.in_dir)
    out_dir = pathlib.Path(args.out_dir)
    if not out_dir.exists():
        out_dir.mkdir(parents=True, exist_ok=True)

    if str(in_dir) == str(out_dir):
        print('Input and output directories are the same, will use no-overwrite mode')

    try:
        with open(args.in_file, mode='rt', encoding='utf-8') as f:
            print('Opened input file with flags:', args.in_file)
            for line in f:
                line = line.strip()
                if len(line) < 1:
                    continue
                if line[0] == '#':
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                pn = parts[0]
                useflag = parts[1]

                add_useflag(in_dir, out_dir, pn, useflag)
            f.close()

        # Output some statistics
        global g_new_files
        global g_modified_files

        print('Modified files ({}): '.format(len(g_modified_files)))
        for s in g_modified_files:
            print('    {}'.format(s))
        print('New files ({}): '.format(len(g_new_files)))
        for s in g_new_files:
            print('    {}'.format(s))
        
        print('Please run etc-update or dispatch-conf to apply configuration changes.')
        print('(Also remove all /etc/portage/package.use/*.new files)')
    except IOError:
        print('ERROR: Failed to open input file with flags:', args.in_file, file=sys.stderr)


if __name__ == '__main__':
    main()
