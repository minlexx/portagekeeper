#!/usr/bin/python3.5
import sys


def main():
    try:
        numlines = 0
        fo = open('plist.txt', mode='wt', encoding='utf-8')

        with open('world_rebuild.txt', mode='rt', encoding='utf-8') as fi:
            for line in fi:
                line = line.strip()
                if line == '':
                    continue
                if not line.startswith('[ebuild'):
                    continue
                pos = line.find('] ')
                if pos == 0:
                    continue
                pos += 2
                line = line[pos:]
                pos2 = line.find('  ')
                line = line[:pos2]
                pos2 = line.find('::')
                line = line[:pos2]
                print(line)

                fo.write('={} '.format(line))
                numlines += 1

        fo.close()
        print('Lines written: {}'.format(numlines))

    except IOError as ioe:
        print(str(ioe), file=sys.stderr)

if __name__ == '__main__':
    main()
