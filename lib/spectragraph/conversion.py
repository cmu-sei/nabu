"""
    Contains functions for the conversion of the parsed edge list to the different graph algorithms.
"""

"""
    Create a normalized edge list where vertices are numbered 0-n rather than using object numbers
"""
def normalize_edge_list (e, v = None):
    """ the normalized edge list """
    n = []
    
    """
        Get the unique vertices of the graph. The index of a vertex in this 
        list will be used as its normalized label.
    """
    if not v:
        print "not v"
        v = find_v_list (e)

    for a, b in e:
        n.append((v.index(a), v.index(b)))

    return n

def find_v_list (e) :
    v = []
    for a, b in e:
        if a not in v:
            v.append(a)
        if b not in v:
            v.append(b)

    return v



""" test """
if __name__ == "__main__":
    e = [(0,1), (1,3), (0, 5)]
    v = find_v_list(e)
    print normalize_edge_list(e)