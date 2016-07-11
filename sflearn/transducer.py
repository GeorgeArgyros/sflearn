#!/usr/bin/env python
"""
Implementation of a Transducer class. Supports simple methods of consuming
input while producing the corresponding output. Main advantage of the class
is that it can be used to construct lookahead transducers that consume more
than one symbols in a single step.
"""

from sys import argv
from operator import attrgetter

# Defines the empty transition constant
EPSILON = 0xffff

class FstState(object):

    """
    This class describes a state of the Transducer.

    """

    def __init__(self, sid, initial=False, final=True, arcs=None):
        """
        Args:
            stateid (int) : The index of the state in the state array.
            initial (bool) : Whether the state is the initial state
            final (bool) : Whether the state is a final state
            arcs (list) :  List of transitions for the state.
        """
        self.stateid = sid
        self.initial = initial
        self.final = final
        self.arcs = arcs or []


class FstArc(object):

    """
    This class describes an arc (transition) of the Transducer.

    """

    def __init__(self, srcstate, dststate, ilabel, olabel):
        """
        Args:
            srcstate (int) : Index of source state in the state array.
            dststate (int) : Index of destination state in the state array.
            ilabel (list) : Input for which the transition is taken
            olabel (list) : Output emitted if transition is taken
        """
        self.ilabel = ilabel
        self.olabel = olabel
        self.nextstate = dststate
        self.srcstate = srcstate


class Transducer(object):
    """
    Contains extra method to consume input and save/load machines.
    All alphabets must be lists of integers.
    """
    def __init__(self):
        self.states = [FstState(0)]
        self.states[0].initial = True
        self.I = set([])


    def __getitem__(self, i):
        """
        Return the i-th state of the transducer.
        Args:
            i (int) : index of state
        """
        return self.states[i]


    def add_arc(self, src, dst, inp, out):
        """
        Add a transition to the transducer.

        Args:
            src (int) : index of source state.
            dst (int) : index of destination state.
            inp (list) : input consumed by the transition.
            out (list) : Output produced by the transition.
        """
        for s_idx in [src, dst]:
            if s_idx >= len(self.states):
                for i in range(len(self.states), s_idx+1):
                    self.states.append(FstState(i))
        new_arc = FstArc(src, dst, inp, out)
        self.states[src].arcs.append(new_arc)


    def consume_input(self, inp):
        """
        Return the output of the machine for input inp.

        Args:
            inp (list): Input to the transducer.
        Returns:
            list: Output generated for the input.

        """
        inp = list(inp)
        out = []
        state = self.states[0]
        i = 0
        while i != len(inp):
            found = False
            for arc in sorted(state.arcs, key=lambda x: len(x.ilabel), \
                              reverse=True):
                if inp[i:i+len(arc.ilabel)] == arc.ilabel:
                    if arc.olabel != [EPSILON]:
                        out.extend(arc.olabel)
                    state = self.states[arc.nextstate]
                    found = True
                    i += len(arc.ilabel)
                    break
            if not found:
                raise Exception('Invalid Input: {}'.format(inp))
        return out


    def save(self, filename):
        """
        Save the transducer in text format. The arcs of the transducer are saved
        in the form:
            [src] [dest] [ilabel] [olabel]
        The input and output for a transition are saved as comma-seperated
        numbers. If a state is final then the index of the state is added in a
        single line.

        Args:
            filename (str): Filename to save the transducer in
        """
        f = open(filename, 'w+')
        states = sorted(self.states, key=attrgetter('initial'), reverse=True)
        for state in states:
            for arc in state.arcs:
                itext = arc.ilabel
                inp = "{}".format(itext[0])
                for c in itext[1:]:
                    inp += ",{}".format(c)
                otext = arc.olabel
                if not otext:
                    out = str(EPSILON)
                else:
                    out = "{}".format(otext[0])
                    for c in otext[1:]:
                        out += ",{}".format(c)
                f.write('{}\t{}\t{}\t{}\n'.format(state.stateid, arc.nextstate,
                                                  inp, out))
            if state.final:
                f.write('{}\n'.format(state.stateid))
        f.close()


    def load(self, filename):
        """
        Load a transducer saved in text format (see save method).

        Args:
            filename (str): Filename to load the transducer from.
        """
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                arc_entry = line.split()
                if len(arc_entry) == 1:
                    self.__getitem__(int(arc_entry[0])).final = True
                else:
                    ilabel = [int(x) for x in arc_entry[2].split(',')]
                    olabel = [int(x) for x in arc_entry[3].split(',')]
                    self.add_arc(int(arc_entry[0]), int(arc_entry[1]), ilabel, \
                                 olabel)
                    self.I |= set([i for i in ilabel])


def main():
    """
    Transducer usage example.
    """
    trd = Transducer()
    trd.load('transducer.txt')
    inp = [int(x) for x in argv[1:]]
    print 'Input: {}\nOutput: {}'.format(inp, trd.consume_input(inp))


if __name__ == '__main__':
    main()
