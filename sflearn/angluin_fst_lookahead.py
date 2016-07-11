#!/usr/bin/env python
"""
This module contains the class TransducerLearner which implements the algorithm
to infer deterministic transducers with bounded lookahead.

For details see the paper
* Back in Black: Towards Formal, Black-Box Analysis of Sanitizers and Filters
    George Argyros, Ioannis Stais, Angelos D. Keromytis and Aggelos Kiayias
"""

import logging
from os.path import commonprefix
from itertools import product

from transducer import Transducer, EPSILON

def _remove_common_prefix(main, prefix):
    """
    Return the suffix of main after removing its common prefix with "prefix"
    Args:
        main (list): List to return suffix
        prefix (list): list to match prefix

    Returns:
        list: suffix of main after removing common prefix with prefix list.
    """
    common_part = commonprefix([main, prefix])
    return main[len(common_part):]


class _ObservationTable(object):
    """
    This class implements the observation table data structure used by the
    inference algorithm. The table is similar in structure with the one used
    for Mealy Machine inference with the addition of a list with lookahead
    transitions.
    """
    def __init__(self, I):
        """
        Args:
            I (list): input alphabet
        """
        self.ot = {}
        self.access_strings = []
        self.transitions = []
        self.dist_strings = I
        self.I = I
        self.lookaheads = set([])
        self.equiv_classes = {}


    def add_lookahead_transition(self, src, inp, out):
        """
        Adds a lookahead transition in the corresponding list of the observation
        table. If the transition is already in the table will act as a NOP.

        Args:
            src (tuple(int)): Tuple of src access string, should also be part
            of self.access_strings
            inp (tuple(int)): Tuple containing the lookahead input consumed by
            the transition.
            out (tuple(int)): Tuple containing the output emitted by the
            transition.
        """
        if (src, inp, out) in self.lookaheads:
            logging.debug('Lookahead (%s, %s, %s) already in table, skipping.',
                          src, inp, out)
            return False
        logging.debug('Adding Lookahead (%s, %s, %s)', src, inp, out)
        self.lookaheads.add((src, inp, out))
        return True


    def _get_difference(self, trans, acc_str):
        """
        Return a distinguishing string for state reached by trans and state
        reached by acc_str. Used for logging purposes.

        Args:
            trans (tuple(int)): transition to check.
            acc_str(tuple(int)): access string to check.

        Returns:
            list: Distiguishing string for trans, acc_str or None if none is
            found.
        """
        for col in self.dist_strings:
            if self.ot[trans][col] != self.ot[acc_str][col]:
                return col
        return None


    def is_closed(self):
        """
        Check if the observation table is closed.

        Returns:
            tuple(bool, str): True,None if table is closed, otherwise False,s
            is returned where s is an escaping string.
        """
        for trans in self.transitions + \
                 [src+inp for (src, inp, _) in self.lookaheads]:
            found = False
            for acc_str in self.access_strings:
                if self.ot[acc_str] == self.ot[trans]:
                    self.equiv_classes[trans] = acc_str
                    found = True
                    break
            if not found:
                logging.debug('Transition %s is escaping', trans)
                for acc_str in self.access_strings:
                    col = self._get_difference(trans, acc_str)
                    logging.debug('%s with %s are different in %s : %s - %s',
                                  trans, acc_str, col, self.ot[trans][col],
                                  self.ot[acc_str][col])
                return False, trans
        return True, None


    def __getitem__(self, key):
        """
        Return an entry from the observation table.

        Args:
            key (tuple(tuple(int),tuple(int))): A tuple containing the row
            and column of the table respectively, where rows and columns are
            also encoded as tuples of integers.

        Returns:
            list: The entry of the table at the requested position.
        """
        row, col = key
        try:
            return self.ot[row][col]
        except KeyError:
            return None

    def __setitem__(self, key, value):
        """
        Sets the position of the table specified by key at value.

        Args:
            key (tuple(tuple(int),tuple(int))): A tuple containing the row
            and column of the table respectively, where rows and columns are
            also encoded as tuples of integers.
            value (list): The value to set the table entry.
        """
        row, col = key
        if row not in self.ot:
            self.ot[row] = {}
        self.ot[row][col] = value


class TransducerLearner(object):
    """
    This class implements the learning algorithm for transducers with bounded
    lookahead. For more details on the algorith see the paper
    * Back in Black: Towards Formal, Black-Box Analysis of Sanitizers and Filters
        George Argyros, Ioannis Stais, Angelos D. Keromytis and Aggelos Kiayias

    This class is abstract. In order to use it, one should inherit the class
    and implement the membership_query and equivalence_query methods. See the
    methods description for details.

    To use the class afterwards, one should give the alphabet which the machine
    used in the class constructor and then call the learn_transducer() method
    which will learn a model of the transducer returning an instance of the
    Transducer() class.


    """
    def __init__(self, I, loglevel=logging.DEBUG, logfile='learn_fst.log'):
        """
        Args:
            I (list): The input alphabet for the machine. A list of integers.
            loglevel: See logging module documentation.
            logfile (str): File to save logs.
        """
        #Initialize the logging for the algorithm.
        logging.basicConfig(filename=logfile,
                            format='%(asctime)s:%(levelname)s: %(message)s',
                            filemode='w', # Overwrite any old log files
                            level=loglevel)

        # Initialize the observation table with the inpur alphabet
        self.I = I
        self.ot = _ObservationTable(I)
        self._hypothesis = None


    def membership_query(self, inp):
        """
        Abstract method, it should implement the membership query. On input
        a string s the method must return the output of the target Mealy
        Machine on that string.

        Args:
            inp (list): Input for the target mealy machine.
        Returns:
            list: Output of the target machine on input inp.
        """
        raise NotImplementedError('Membership Query method is not implemented')


    def equivalence_query(self, hypothesis):
        """
        Abstract method, it should implement equivalence query. In systems
        where an equivalence query is unavailable a search strategy should
        be implemented to search for counterexamples. In absence of a
        counterexample one should assume that the machine is correct.

        Args:
            hypothesis(Transducer): The hypothesis to test for correctness.

        Returns:
            tuple(bool, list): True, None if the hypothesis is found to be
            correct, or False, ce where ce is an input where the hypothesis
            and target machine disagree.
        """
        raise NotImplementedError('Equivalence Query method is not implemented')


    def _fill_ot_entry(self, row, col):
        """
        Fill an entry of the observation table.
        Only save the part of the output generated by the col parameter.

        Args:
            row(tuple(int)): A tuple of integers specifiying the row to fill.
            col(tuple(int)): A tuple of integers specifying the column to fill.
        """

        prefix = self.membership_query(row)
        full_output = self.membership_query(row + col)

        prefix_len = len(commonprefix([prefix, full_output]))
        self.ot[row, col] = full_output[prefix_len:]


    def _check_lookahead(self, inp):
        """
        Check a counterexample for lookahead transitions using prefix-closed
        queries. If an unknown lookahead is found it is added on the observation
        table.

        Args:
            inp (list): Counterexample input.
        """
        # Make a prefix closed membership query and gather the result
        prefix = []
        prefix_set = [[]]
        prefix_set_input = [[]]
        for c in inp:
            prefix.append(c)
            prefix_set_input.append(prefix)
            prefix_set.append(self.membership_query(prefix))

        for i in xrange(1, len(prefix_set)):
            if commonprefix([prefix_set[i], prefix_set[i-1]]) != prefix_set[i-1]:
                logging.debug('Lookahead detected at position %s : %s, %s',
                              i, prefix_set[i-1], prefix_set[i])

                la_out = _remove_common_prefix(prefix_set[i], prefix_set[i-1])
                j = None
                for j in reversed(xrange(i)):
                    if commonprefix([prefix_set[i], prefix_set[j]]) == prefix_set[j]:
                        la_inp = inp[j:i]
                        break

                la_out = _remove_common_prefix(prefix_set[i], prefix_set[j])
                access_string = self._run_in_hypothesis(inp, j)
                out_as = self.membership_query(access_string)
                out_complete = self.membership_query(list(access_string)+la_inp)

                # If The access string for the lookahead state is wrong, we will
                # add the lookahead path once this is fixed in a next iteration.
                if _remove_common_prefix(out_complete, out_as) != la_out:
                    logging.debug('Lookahead detected but access string is '+ \
                                  'wrong, skipping.')
                    continue
                if  self.ot.add_lookahead_transition(access_string,
                                                     tuple(la_inp),
                                                     tuple(la_out)):
                    # Fill all table entries for the lookahead transition
                    for col in self.ot.dist_strings:
                        self._fill_ot_entry(access_string + tuple(la_inp), col)
                    # New lookahead added, no need for further processing.
                    break


    def _run_in_hypothesis(self, inp, index):
        """""
        Run the string in the hypothesis automaton for index steps and then
        return the access string for the state reached.

        Args:
            inp(list): Input to run the machine on.
            index(int): How many steps to execute.

        Returns:
            tuple (int): A tuple containing the access string for the state
            reached by running the machine.
        """
        state = self._hypothesis[0]
        s_index = 0
        i = 0
        while i != len(inp) and i < index:
            found = False
            for arc in sorted(state.arcs, key=lambda x: len(x.ilabel),
                              reverse=True):
                if inp[i:i+len(arc.ilabel)] == arc.ilabel:
                    state = self._hypothesis.states[arc.nextstate]
                    s_index = arc.nextstate
                    found = True
                    i += len(arc.ilabel)
                    break
            if not found:
                raise Exception('Invalid Input: {}'.format(inp))

        # The id of the state is its index inside the access_strings list
        access_string = self.ot.access_strings[s_index]
        return access_string


    def _process_counterexample(self, ce):
        """
        Counterexample processing method. The method is similar with the
        Shabaz-Groz counterexample processing with an additional module to
        check for counterexamples resulting from lookahead transitions.

        Args:
            ce (list): counterexample input
        """
        # Process lookaheads
        self._check_lookahead(ce)

        #Finding longest prefix among strings in S_m
        maxlen = 0
        for row in self.ot.access_strings:
            if not row:
                continue
            # Seems that commonprefix works for tuple/list pairs but convert
            # just to be sure.
            prefix = commonprefix([ce, list(row)])
            if len(prefix) > maxlen:
                maxlen = len(prefix)

        # Add the all the suffixes as experiments in E_m
        suff = ()
        for c in reversed(ce[maxlen:]):
            suff = (c,) + suff
            # Add the experiment if not already there
            if suff not in self.ot.dist_strings:
                self.ot.dist_strings.append(suff)

            # Fill the entries in the observation table
            for row in self.ot.access_strings + self.ot.transitions:
                self._fill_ot_entry(row, suff)

            # Fill the lookahead transitions
            for (src, inp, _) in self.ot.lookaheads:
                self._fill_ot_entry(src+inp, suff)


    def _close_ot(self, escaping_str):
        """
        Given a transition escaping_str in transitions that is not equivalent with any
        access_string this method will move that transition in access_strings
        and create all corresponding transitions in the table.

        Args:
            escaping_str (tuple(int)): escaping transition
        """
        self.ot.access_strings.append(escaping_str)
        for i in self.I:
            self.ot.transitions.append(escaping_str + (i,))
            for dist in self.ot.dist_strings:
                self._fill_ot_entry(escaping_str + (i,), dist)


    def _construct_hypothesis(self):
        """
        Utilize the observation table to construct a Mealy Machine.

        Returns:
            Transducer: A mealy machine build based on a closed and consistent
            observation table.
        """
        hypothesis = Transducer()
        for acc_str in self.ot.access_strings:
            for i in self.I:
                dst = self.ot.equiv_classes[acc_str + (i,)]
                # If dst == None then the table is not closed.
                if dst is None:
                    logging.debug('Conjecture attempt on non closed table.')
                    return None
                out = self.ot[acc_str, (i, )]
                src_id = self.ot.access_strings.index(acc_str)
                dst_id = self.ot.access_strings.index(dst)
                if not self.ot[acc_str, (i, )]:
                    out = [EPSILON]
                else:
                    out = [int(x) for x in self.ot[acc_str, (i, )]]
                hypothesis.add_arc(src_id, dst_id, [int(i)], out)

        # add the transitions from the lookahead list
        for (src, inp, out) in self.ot.lookaheads:
            dst = self.ot.equiv_classes[src+inp]
            src_id = self.ot.access_strings.index(src)
            dst_id = self.ot.access_strings.index(dst)
            hypothesis.add_arc(src_id, dst_id, list(inp), list(out))

        # This is for format compatibility with the DFA/SFAs.
        for state in hypothesis.states:
            state.final = True
        return hypothesis


    def _init_ot(self):
        """
        Initialize the observation table.
        """
        self.ot.access_strings.append(())
        self.ot.transitions = [(x,) for x in list(self.I)]
        self.ot.dist_strings = [(x,) for x in list(self.I)]

        for dist in self.ot.dist_strings:
            self._fill_ot_entry((), dist)

        for trans, dist in product(self.ot.transitions, self.ot.dist_strings):
            self._fill_ot_entry(trans, dist)


    def learn_transducer(self):
        """
        Implements the high level logic of the algorithm to infer a transducer
        with bounded lookahead.

        Returns:
            Transducer: A model for the target mealy machine.
        """
        logging.info('Initializing learning procedure.')
        self._init_ot()

        logging.info('Generating a closed and consistent observation table.')
        while True:

            closed = False
            # Make sure that the table is closed and consistent
            while not closed:

                logging.debug('Checking if table is closed.')
                closed, escaping_str = self.ot.is_closed()
                if not closed:
                    logging.debug('Closing table.')
                    self._close_ot(escaping_str)
                else:
                    logging.debug('Table closed.')

            # Create conjecture
            self._hypothesis = self._construct_hypothesis()

            logging.info('Generated conjecture machine with %d states.',
                         len(self._hypothesis.states))

            # Check correctness
            logging.debug('Running equivalence query.')
            found, ce = self.equivalence_query(self._hypothesis)

            # Are we done?
            if found:
                logging.info('No counterexample found. Hypothesis is correct!')
                break

            # Add the new experiments into the table to reiterate the
            # learning loop
            logging.info('Processing counterexample %s with length %d.', ce, len(ce))
            self._process_counterexample(ce)

        logging.info('Learning complete.')
        return self._hypothesis


if __name__ == '__main__':
    print 'Inference for Transducer with bounded lookahead: abstract ' + \
            'class implementation.'
