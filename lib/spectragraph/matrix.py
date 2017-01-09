from array import array


class SimpleMatrix(object):

    def __init__(self, r, c=None):
        if not c:
            c = r
        self.rows = r
        self.cols = c
        self.size = self.rows * self.cols
        self.elements = [array('B', (0 for col in range(self.cols))) for row in range(self.rows)]

    def grow(self, r, c=None):
        if not c:
            c = r
        self.rows += r
        self.cols += c
        for row in range(self.rows):
            try:
                self.elements[row].extend([0 for i in range(c)])
            except IndexError:
                self.elements.append(array('B', (0 for col in range(self.cols))))

    def __len__(self):
        return self.size

    def __getitem__(self, key):
        return self.elements[key]

    def __setitem__(self, key, value):
        self.elements[key] = value

    def __delitem__(self, key):
        self.elements[key] = array('B', [0 for col in range(self.cols)])

    def __iter__(self):
        return iter(self.elements)

    def __str__(self):
        rv = ["  %s" % ' '.join([str(i) for i in range(self.cols)])]
        for idx, row in enumerate(self.elements):
            rv.append("%d %s" % (idx, ' '.join([str(i) for i in row])))
        return '\n'.join(rv)


if __name__ == "__main__":
    from timeit import timeit
    from random import randint

    m = SimpleMatrix(100)

    print "Size:", m.size
    print " Len:", len(m)
    assert(m.size == len(m))

    for i in range(100):
        for j in range(100):
            r = randint(0, 255)
            m[i][j] = r
            assert (m[i][j] == r)

    for i in range(100):
        for j in range(100):
            print m[i][j],
        print

    for i in range(100):
        del m[i]

    for row in m:
        for col in row:
            print col,
            assert(not col)
        print

    def create_matrix(r, c):
        SimpleMatrix(r, c)

    for i in range(5):
        i *= 10
        print timeit("create_matrix(%d, %d)" % (i, i), setup="from __main__ import create_matrix", number=10)

