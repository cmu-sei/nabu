import logging
import networkx as nx
import sys
from matrix import SimpleMatrix


"""

Vertex = (idx, label, attrs, weight)

"""
V_IDX = 0
V_LABEL = 1
V_ATTRS = 2
V_WEIGHT = 3


class Graph(object):

    def __init__(self):
        self.v = []
        self.matrix = None
        self.order = 0
        self.size = 0
        self.cliques = []
        self.clique_weights = []

    @staticmethod
    def jaccard_coef(intersection, union):
        return float(intersection)/(union-intersection)

    @staticmethod
    def vertex_weight(v1, v2):
        vattrs = V_ATTRS
        try:
            weight = float(len(set(v1[vattrs]).intersection(v2[vattrs])))/len(set(v1[vattrs]).union(v2[vattrs]))
        except ZeroDivisionError:
            weight = 0.0
        return weight

    @staticmethod
    def make_vertex(idx, label, attrs=None, weight=0.0):
        if not attrs:
            attrs = []
        return idx, label, attrs, weight

    def init(self, v, e):
        self.init_vertices(v)
        self.init_matrix(self.order)
        self.init_edges(e)

    def init_vertices(self, v):
        self.v = []
        for idx, vert in enumerate(v):
            self.v.append(self.make_vertex(idx, *vert))
        self.order = len(self.v)

    def init_matrix(self, order):
        self.matrix = SimpleMatrix(order)

    def init_edges(self, e):
        self.size = len(e)
        vmap = dict()
        start_order = self.order
        for src, dst in e:
            sidx = vmap.get(src)
            if not sidx:
                sidx = self.v_by_label(src)
                if sidx < 0:
                    logging.warning("Graph.init_edges: Uknown src vertex added %s" % str(src))
                    sidx = self.add_vertex(src)
                vmap[src] = sidx
            didx = vmap.get(dst)
            if not didx:
                didx = self.v_by_label(dst)
                if didx < 0:
                    logging.warning("Graph.init_edges: Uknown dst vertex added %s" % str(dst))
                    didx = self.add_vertex(dst)
                vmap[dst] = didx

        new_verts = self.order - start_order
        if new_verts:
            self.matrix.grow(new_verts)

        for src, dst in e:
            sidx = vmap.get(src)
            didx = vmap.get(dst)
            self.matrix[sidx][didx] = 1
            self.matrix[didx][sidx] = 1

    def add_vertex(self, label):
        self.v.append(self.make_vertex(len(self.v), label))
        new_idx = self.order
        self.order += 1
        return new_idx

    def v_by_label(self, label):
        vlabel = V_LABEL
        rv = -1
        for vertex in self.v:
            if vertex[vlabel] == label:
                rv = vertex[V_IDX]
                break
        return rv

    def adjacent(self, v1, v2):
        v1 = self.v_by_label(v1)
        v2 = self.v_by_label(v2)
        if v1 == v2:
            return 0
        return self.matrix[v1][v2]

    def neighbors(self, v_idx):
        return [idx for idx, edge in enumerate(self.matrix[v_idx]) if edge]

    def bron_kerbosch(self, r, p, x):
        if not p and not x:
            self.cliques.append(r)
            return
        while p:
            vert = p.pop()
            n = set(self.neighbors(vert))
            self.bron_kerbosch(r.union({vert}), p.intersection(n), x.intersection(n))
            x.add(vert)

    def get_pivot(self, p, x):
        max_n = []
        max_v = None
        neighbors = []
        for v in p.union(x):
            neighbors = self.neighbors(v)
            if len(neighbors) >= len(max_n):
                max_n = neighbors
                max_v = v
        return max_v, max_n

    def bron_kerbosch_pivot(self, r, p, x):
        if not p and not x:
            self.cliques.append(r)
            return
        u, n_u = self.get_pivot(p, x)
        for vert in p.difference(set(n_u)):
            n = set(self.neighbors(vert))
            self.bron_kerbosch_pivot(r.union({vert}), p.intersection(n), x.intersection(n))
            x.add(u)

    def degenerate_order(self, verts):
        L = []
        D = [[] for i in range(self.order)]
        dv_map = {}
        for v in verts:
            dv = len(self.neighbors(v))
            dv_map[v] = dv
            D[dv].append(v)

        k = 0

        for x in range(self.order):
            for i, d in enumerate(D):
                if d:
                    k = max(k, i)
                    v = d.pop()
                    L.append(v)
                    for n in self.neighbors(v):
                        if n not in L:
                            dv = dv_map[n]
                            D[dv].remove(n)
                            dv -= 1
                            D[dv].append(n)
                            dv_map[n] = dv
                    break
        return k, L

    def bron_kerbosch_deg_order(self):
        p = set([i for i in range(len(self.v))])
        r = set()
        x = set()
        d, sorted_v = self.degenerate_order(p)
        print "Degenerate order: %d, Vertices: %d" %(d, len(sorted_v))
        for v in sorted_v:
            vset = {v}
            n_v = set(self.neighbors(v))
            self.bron_kerbosch_pivot(r.union(vset), p.intersection(n_v), x.intersection(n_v))
            p.difference_update(vset)
            x.update(vset)

    def __str__(self):
        rv = '['
        rv += '\n '.join([' '.join([str(col) for col in row]) for row in self.matrix])
        rv += ']'
        return rv


class AssocGraph(Graph):
    """
    Vertex = (idx, label, attrs, weight)
    """

    def __init__(self):
        self.e = []
        self.g1order = 0
        self.g2order = 0
        super(AssocGraph, self).__init__()

    @staticmethod
    def combine_verts(verts1, verts2):
        vlabel = V_LABEL
        v = []
        for v1 in verts1:
            for v2 in verts2:
                weight = AssocGraph.vertex_weight(v1, v2)
                v.append(((v1[vlabel], v2[vlabel]), None, weight))
        return v

    @staticmethod
    def find_edges(v, g1, g2):
        vlabel = V_LABEL - 1
        edges = []
        for vert1 in v:
            for vert2 in v:
                ag_v1 = vert1[vlabel]
                ag_v2 = vert2[vlabel]
                a1 = ag_v1[0]
                a2 = ag_v1[1]
                b1 = ag_v2[0]
                b2 = ag_v2[1]
                if a1 == b1 or a2 == b2:
                    continue
                if (g1.adjacent(a1, b1) and g2.adjacent(a2, b2)) \
                        or (not g1.adjacent(a1, b1) and not g2.adjacent(a2, b2)):
                    edges.append((ag_v1, ag_v2))
        return edges

    def associate(self, g1, g2):
        self.g1order = g1.order
        self.g2order = g2.order
        v = self.combine_verts(g1.v, g2.v)
        e = self.find_edges(v, g1, g2)
        self.e = e
        self.init(v, e)

    def clique_weight(self, clique):
        vweight = V_WEIGHT
        return sum([self.v[v_idx][vweight] for v_idx in clique])

    def calc_clique_weights(self):
        self.clique_weights = [self.clique_weight(c) for c in self.cliques]

    def nx_sim_score(self):
        g = nx.Graph()
        print "Vertices: %d" % len(self.v)
        for node in self.v:
            n = node[V_LABEL]
            g.add_node(n)
        print "Edges: %d" % len(self.e)
        for edge in self.e:
            g.add_edge(*edge)
        maxw = 0
        maxc = []
        cnt = 0
        sys.stdout.write("%d\r" % cnt)
        '''
        for clique in nx.find_cliques(g):
            sys.stdout.write("%d\r" % cnt)
            w = self.clique_weight([self.v_by_label(c) for c in clique])
            if w > maxw:
                maxw = w
                maxc = clique
        '''
        from networkx.algorithms.approximation import max_clique, clique_removal
        for c in clique_removal(g)[1]:
            if len(c) > len(maxc):
                maxc = c
        maxw = self.clique_weight([self.v_by_label(c) for c in maxc])
        jscore = self.jaccard_coef(len(maxc), self.g1order + self.g2order)
        wscore = maxw / self.g1order
        print "MaxW", maxw
        print "JScore %d, %d", len(maxc), self.g1order+self.g2order, jscore
        print "Wscore", wscore
        return jscore, wscore

    def sim_score(self):
        vlabel = V_LABEL
        logging.debug("Starting BK Pivot")
        self.bron_kerbosch_deg_order()  #r=set(), p=set([i for i in range(len(self.v))]), x=set())
        logging.debug("Calculating clique weights")
        self.calc_clique_weights()
        mcl_weight = max(self.clique_weights)
        logging.debug("Max weight: %d" % mcl_weight)
        mcl_idx = self.clique_weights.index(mcl_weight)
        mcs = set([self.v[i][vlabel][0] for i in self.cliques[mcl_idx]])
        print self.cliques[mcl_idx]
        jscore = self.jaccard_coef(len(mcs), self.g1order + self.g2order)
        weightscore = mcl_weight / self.g1order
        return jscore, weightscore

    def __str__(self):
        rv = ""
        for idx, vert in enumerate(self.v):
            rv += "[%d](%s, %s) " % (idx, vert[V_LABEL][0], vert[V_LABEL][1])
        return rv


def main():
    import sys
    import networkx as nx
    import pydot
    import pygraphviz as pgv
    import matplotlib.pyplot as plt

    g1v = [('A1', ['a']),
           ('A2', ['b', 'a']),
           ('A3', ['a', 'c'])]
    g2v = [('B1', ['a']),
           ('B2', ['b', 'a']),
           ('B3', ['x', 'y'])]
    g3v = [('C1', ['a']),
           ('C2', ['b', 'a']),
           ('C3', ['a', 'c'])]
    g4v = [('1', ['a']),
           ('2', ['a']),
           ('3', ['a']),
           ('4', ['a']),
           ('5', ['a']),
           ('6', ['a'])]

    g1e = [('A1', 'A2'), ('A2', 'A3')]
    g2e = [('B1', 'B2'), ('B2', 'B3')]
    g3e = [('C1', 'C2'), ('C2', 'C3')]
    g4e = [('1', '2'),
           ('1', '5'),
           ('2', '5'),
           ('2', '1'),
           ('2', '3'),
           ('3', '4'),
           ('3', '2'),
           ('4', '3'),
           ('4', '6'),
           ('4', '5'),
           ('5', '4'),
           ('5', '2'),
           ('5', '1'),
           ('6', '4')]

    g1 = Graph()
    g2 = Graph()
    g3 = Graph()
    g4 = Graph()

    g1.init(g1v, g1e)
    g2.init(g2v, g2e)
    g3.init(g3v, g3e)
    g4.init(g4v, g4e)

    ag1 = AssocGraph()
    ag2 = AssocGraph()

    ag1.associate(g1, g2)
    ag2.associate(g1, g3)

    print g1
    print g2
    print g3
    print ag1
    print ag2

    sys.stdout.write("%f, %f\n" % ag1.sim_score())
    sys.stdout.write("%f, %f\n" % ag2.sim_score())

    g4.bron_kerbosch_pivot(r=set(), p=set([i for i in range(len(g4.v))]), x=set())
    print "G4 cliques"
    for c in g4.cliques:
        for v in c:
            print g4.v[v][1],
        print

    g4.cliques = []
    g4.clique_weights = []
    g4.bron_kerbosch_deg_order()
    print "G4 cliques with degenerate order",g4.cliques
    for c in g4.cliques:
        for v in c:
            print g4.v[v][1],
        print

    print "NetworkX Tests"
    nxg1 = nx.Graph()
    nxg2 = nx.Graph()

    for n in g1v:
        nxg1.add_node(n[0], attr_dict={"label": str(n[0])})
    for n in g2v:
        nxg2.add_node(n[0], attr_dict={"label": str(n[0])})
    for e in g1e:
        nxg1.add_edge(*e)
    for e in g2e:
        nxg2.add_edge(*e)

    contrived_ag_nodes = range(9)
    contrived_ag_edges = [(0,4), (0,8),
        (1,3), (1,5),
        (2,6), (2,4),
        (3,1), (3,7),
        (4,0), (4,2), (4,6), (4,8),
        (5,1), (5,7),
        (6,2), (6,4),
        (7,3), (7,5),
        (8,4), (8,0)]


    nxag1 = nx.Graph()
    for i, node in enumerate(contrived_ag_nodes):
        x = float(i * 100 % 300)
        y = float(i / 3 * 100 % 300)
        nxag1.add_node(node, attr_dict={"label": str(node), "pos": "%f, %f" % (x,y)})

    for edge in contrived_ag_edges:
        nxag1.add_edge(*edge)

    pgvag1 = nx.to_agraph(nxag1)
    pgvag1.graph_attr['overlap'] = 'true'
    pgvag1.layout()
    pgvag1.draw("spectragraph.png")

    #labels = nx.draw_networkx_labels(nxag1, pos=nx.spring_layout(nxag1), labels=dict(zip(range(9), range(9))))
    #nx.draw(nxag1, with_labels=True, labels=labels)

    pydot_ag1 = nx.to_pydot(nxag1)
    print pydot_ag1.to_string()

    for c in nx.find_cliques(nxag1):
        print c

    tensor = nx.tensor_product(nxg1, nxg2)
    nx.draw(tensor)
    pgvag2 = nx.to_agraph(tensor)
    pgvag2.layout()
    pgvag2.draw("tensor.png")

if __name__ == "__main__":
    main()
