#!/usr/bin/env python
"""
This module implements the BekProgram class which is used to convert
Transducer() objects into BEK programs.
"""
from sys import argv
from collections import defaultdict
from operator import attrgetter
from  transducer import Transducer, EPSILON

class _BekState(object):
    """
    Simple storage class, it holds information regarding the lookahead path
    each BEK state process.
    """
    def __init__(self):
        self.la_trans_list = set([])
        self.prefix = []
        self.prefix_out = []


class BekProgram(object):
    """
    Implements a compiler to transform Transducer objects into BEK programs
    which can then be further analyzed using the BEK infrastructure. For more
    information see http://rise4fun.com/Bek/tutorial.

    The main public method is create_from_transducer() which will compile the
    BEK program from a transducer which can then be accessed in the bek_program
    public variable.
    """
    def __init__(self, name='sanitizer'):
        """
        Args:
            name (str): BEK program name.
        """
        self.program_name = name
        self.transducer = None
        self.bek_program = None
        self._state_info = None


    @staticmethod
    def _generate_yield_text(otext):
        """
        Given an input text generate a yield statement for that text in the
        BEK language

        Args:
            otext (list): text to generate yield statement.
        Returns:
            str: yield statement in BEK language.
        """
        if otext != [EPSILON]:
            yld = 'yield({}'.format(otext[0])
            for c in otext[1:]:
                yld += ",{}".format(c)
            yld += ");"
        else:
            yld = ''
        return yld


    @staticmethod
    def _get_most_frequent_transition(state):
        """
        Args:
            state (FstState): state to analyze
        Returns:
            list, int: The output and next state of the most common transition
            for the input state. If the most common transition is the identity
            function then 'c',dst is returned.
        """
        arc_count = defaultdict(int)
        for arc in state.arcs:
            # Avoid generalizing to lookahead transitions to avoid weird corner
            # cases
            if len(arc.ilabel) > 1:
                continue
            # If ilabel == olabel then we have identity function. This is
            # generalized differently by outputing the input character directly
            if arc.ilabel != arc.olabel:
                arc_count[(tuple(arc.olabel), arc.nextstate)] += 1
            else:
                arc_count[('c', arc.nextstate)] += 1

        # Collect the most frequent input/output pair
        ((out, dst), _) = sorted(arc_count.iteritems(), key=lambda x: x[1],
                                 reverse=True)[0]
        return (list(out), dst)


    @staticmethod
    def _is_symbolic_trans(out, stateid, arc):
        """
        Args:
            out (list): output of symbolic transition
            stateid (int): destination state of symbolic transition
            arc (FstArc): transition to be checked if it belongs to symbolic
            transitions.
        Returns:
            True if arc can be grouped with the symbolic transitions, False
            otherwise
        """
        return (out == arc.olabel or \
                (out == ['c'] and arc.olabel == arc.ilabel)) \
                and (stateid == arc.nextstate)


    def _parse_lookahead_transition(self, arc):
        """
        Parse a lookahead transition and set the necessary information in the
        states from which this transition will pass if not matched completely.

        Args:
            arc (FstArc): Lookahead arc to parse.
        """
        trans = arc.ilabel
        output = arc.olabel
        src = self.transducer.states[arc.srcstate]
        prefix = []
        prefix_out = []

        inp = list(trans)
        starts = True
        for c in inp:
            for arc in src.arcs:
                # Only process the current lookahead path
                if len(arc.ilabel) > 1:
                    continue
                if arc.ilabel == [c]:
                    la_trans = tuple([c])
                    la_next = arc.nextstate
                    la_prefix = list(prefix)

                    prefix.append(arc.ilabel[0])
                    la_complete = tuple(output) if prefix == inp else None
                    entry = (la_trans, la_next, la_complete, starts)
                    self._state_info[src.stateid].la_trans_list.add(entry)
                    # Only save prefixes for lookahead paths that are running
                    # for at least one state
                    if not starts:
                        self._state_info[src.stateid].prefix = la_prefix
                        self._state_info[src.stateid].prefix_out = list(prefix_out)
                    prefix_out += arc.olabel
                    src = self.transducer.states[arc.nextstate]
                    starts = False
                    break


    def _generate_transition(self, arc):
        """
        produce the text for a normal (non lookahead, non symbolic) transition

        Args:
            arc (FstArc): arc to generate transition from.
        """
        stateid = arc.srcstate
        otext = arc.olabel
        next_prefix_out = self._state_info[arc.nextstate].prefix_out
        prefix_out = self._state_info[stateid].prefix_out

        # Corner case: If the next state emits output and that output matches
        # the output of the arc, then omit generating any output, since it will
        # be produced on the next state.
        if  next_prefix_out == arc.olabel:
            otext = []

        # If there was an umatched lookahead path consumed up to this state
        # then prepend the output produced up to this prefix.
        if prefix_out:
            otext = prefix_out + otext
        yld = self._generate_yield_text(otext)
        return "if (c == {}){{s:={}; {}}}\n".format(arc.ilabel[0],
                                                    arc.nextstate, yld)


    def _set_transducer_lookahead_info(self):
        """
        Fills the _state_info table with the necessary information regarding
        the lookahead paths of the transducer.
        """
        self._state_info = {sid : _BekState() for sid in \
                           xrange(len(self.transducer.states))}
        for state in self.transducer.states:
            for arc in state.arcs:
                if len(arc.ilabel) > 1:
                    self._parse_lookahead_transition(arc)


    def _generate_program_end(self):
        """
        Generate the part of the BEK program that is executed when input
        processing by the main loop is finished. This part is responsible for
        emitting any input that wasn't emitted during input processing due
        to lookahead transitions.
        """
        end_part = " end {\n"
        end_non_empty = False
        for sid in xrange(len(self.transducer.states)):
            la_prefix = self._state_info[sid].prefix_out
            if la_prefix:
                end_non_empty = True
                yld = self._generate_yield_text(la_prefix)
                tmp = "\tcase (s == {}) : {}\n".format(sid, yld)
                end_part += tmp
        end_part += "\t}"
        return end_part if end_non_empty else None


    def _generate_lookahead_transitions(self, state):
        """
        Generate the lookahead transitions for a state.

        Args:
            state (FstState): State for which to generate transitions.
        Returns:
            bool, list, str: Returns a list of the transitions which were
            generated in this function in order to avoid regenerating them
            afterwards.  Moreover, the BEK program text generated is returned
            and whether any transition was generated in this function.
        """
        tmp_program = ''
        la_prefix = self._state_info[state.stateid].prefix_out
        la_trans = None
        first = True
        skip_trans = []
        for (la_trans, la_next, la_compl, la_starts) in \
                self._state_info[state.stateid].la_trans_list:
            skip_trans.append(list(la_trans))
            tmp_program += "\t\t" if first else "\t\telse "
            tmp = 'if (c =={}){{s:={};'.format(la_trans[0], la_next)
            # If this transition completes a lookahead path then generate the
            # output of the path.
            if la_compl:
                tmp += self._generate_yield_text(list(la_compl))
            # If the transition is part of a lookahead path but the path is
            # starting, we need to generated any pending output.
            elif la_prefix and la_starts:
                tmp += self._generate_yield_text(la_prefix)
            tmp += '}\n'
            first = False
            tmp_program += tmp
        return first, skip_trans, tmp_program


    def create_from_transducer(self, transducer, do_symbolic=True):
        """
        Generate a BEK program from the input transducer.

        Args:
            transducer (Transducer): Transducer to compile into BEK program.
            do_symbolic (bool): Whether to generalize into symbols that are
            not explicitly part of the transducer's alphabet
        Returns:
            str: The generated BEK program
        """
        self.transducer = transducer
        self._set_transducer_lookahead_info()
        bek_program = ''

        # Generate program preamble
        bek_program += "program {}(input) {{\n".format(self.program_name)
        bek_program += "\treturn iter(c in input)[s := 0;] {\n"

        # Generate the main loop which iterates through the input
        states = sorted(transducer.states, key=attrgetter('initial'),
                        reverse=True)

        for state in states:
            la_prefix = self._state_info[state.stateid].prefix_out

            bek_program += "\tcase(s == {}):\n".format(state.stateid)

            # Generate transitions which are part of lookahead paths
            first, skip_trans, tmp = self._generate_lookahead_transitions(state)
            bek_program += tmp

            # If we want to generalize the transitions into symbolic ones we
            # find the most frequent transition to generalize
            if do_symbolic:
                sym_out, sym_next = self._get_most_frequent_transition(state)

            # Generate normal transitions, excluding symbolic ones and those
            # which were generated as part of lookahead paths.
            for arc in state.arcs:
                # Symbolic transition will be generated afterwards
                if do_symbolic and self._is_symbolic_trans(sym_out, sym_next, arc):
                    continue

                # Lookahead arcs or arcs that are part of lookahead paths
                # were generated before so we skip them.
                if len(arc.ilabel) > 1 or arc.ilabel in skip_trans:
                    continue

                bek_program += "\t\t" if first else "\t\telse "
                first = False

                # Generate normal transitions
                bek_program += self._generate_transition(arc)

            # The symbolic transition will consume any other input not matching
            # the previously generated transitions. This will include all
            # symbols not specifically set by the transducer given as input as
            # well as inputs
            if do_symbolic:
                yld = self._generate_yield_text(la_prefix + sym_out)
                tmp = "\t\telse {{ s := {}; {} }}\n".format(sym_next, yld)
            else:
                # If we don't have symbolic transitions reject unknown inputs
                tmp = "\t\telse { raise InvalidInput;  }\n"
            bek_program += tmp

        # Generate the final (end {}) part of the BEK program, by printing for
        # each state the output of the lookahead prefix that is consumed when we
        # reach that state
        bek_program += "\t}"
        end_part = self._generate_program_end()
        if end_part:
            bek_program += end_part
        bek_program += "; \n}\n==\n"
        self.bek_program = bek_program
        return bek_program


    def save(self, filename='sanitizer.bek'):
        """
        Saves the generated program into the file given as argument. This
        function requires the function create_from_transducer to be called
        before it can be used.

        Args:
            filename (str): Filename to save the BEK program
        Returns:
            bool: True if saving file is succesful, False otherwise.
        """
        if not self.bek_program:
            return False
        with open(filename, 'w') as f:
            f.write(self.bek_program)
        return True


def main():
    """
    Simple interface to convert transducers from text format to BEK programs
    """
    filename = 'transducer.txt'
    if len(argv) > 1:
        filename = argv[1]

    trans = Transducer()
    trans.load(filename)

    bek = BekProgram()
    bek.create_from_transducer(trans)
    print bek.bek_program


if __name__ == '__main__':
    main()

