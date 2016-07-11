#!/usr/bin/env python
"""
This module contains the class MealyMachineLearner which implements the
L* Algorithm adapted for inferring mealy machines with epsilon-transitions.

For details see the paper
* Back in Black: Towards Formal, Black-Box Analysis of Sanitizers and Filters
    George Argyros, Ioannis Stais, Angelos D. Keromytis and Aggelos Kiayias
"""

import logging

from itertools import product
from os.path import commonprefix
from transducer import Transducer, EPSILON

CE_SG = 0
CE_RS = 1

class _ObservationTable(object):

    """
    This class implements the observation table data structure used by the
    L* algorithm.
    """

    def __init__(self, I):
        """
        Args:
            I (list): input alphabet
        """
        self.ot = {}
        self.access_strings = []
        self.transitions = []
        self.dist_strings = list(I)
        self.equiv_classes = {}

    def is_closed(self):
        """
        Check if the observation table is closed.

        Returns:
            tuple(bool, str): True,None if table is closed, otherwise False,s
            is returned where s is an escaping string.
        """
        for trans in self.transitions:
            found = False
            for acc_str in self.access_strings:
                if self.ot[acc_str] == self.ot[trans]:
                    self.equiv_classes[trans] = acc_str
                    found = True
                    break
            if not found:
                logging.debug('Transition {} is escaping'.format(trans))
                return False, trans
        return True, None


    def __getitem__(self, key):
        """
        Return the requested entry from the observation table.

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


class MealyMachineLearner(object):
    """
    L* Algorithm adapted for inferring mealy machines with epsilon-transitions.

    For details see the paper
    * Back in Black: Towards Formal, Black-Box Analysis of Sanitizers and Filters
        George Argyros, Ioannis Stais, Angelos D. Keromytis and Aggelos Kiayias

    This class is abstract. In order to use it, one should inherit the class
    and implement the membership_query and equivalence_query methods. See the
    methods description for details.

    To use the class afterwards, one should give the alphabet which the machine
    used in the class constructor and then call the learn_mealy_machine()
    method which will infer the mealy machine returning an instance of the
    Transducer() class.

    The class supports two counterexample processing methods, Shabaz-Groz (SG)
    counterexample processing and the adapted Rivest-Schapire (RS) method. By
    default, RS is used since it is exponentially better in terms of query
    utilization than SG.
    """
    def __init__(self, I, loglevel=logging.INFO, logfile='learn_mm.log',
                 ce_processing=CE_RS):
        """
        Args:
            I (list): The input alphabet for the machine. A list of integers.
            loglevel: See logging module documentation.
            logfile (str): File to save logs.
            ce_processing (int): Which counterexample method to use. Use
            CE_RS for Rivest-Schapire and CE_SG for Shabaz-Groz.
        """
        #Initialize the logging for the algorithm.
        logging.basicConfig(filename=logfile,
                            format='%(asctime)s:%(levelname)s: %(message)s',
                            filemode='w', # Overwrite any old log files
                            level=loglevel)

        if ce_processing == CE_SG:
            logging.info('Using Shabaz-Groz counterexample processing.')
            self.process_counterexample = self._process_ce_sg
        elif ce_processing == CE_RS:
            logging.info('Using Rivest-Schapire counterexample processing.')
            self.process_counterexample = self._process_ce_rs
        else:
            raise NotImplementedError('Unsupported counterexample processing')

        # Initialize the observation table with the input alphabet
        self.I = list(I)
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

        common_prefix_len = len(commonprefix([prefix, full_output]))
        self.ot[row, col] = full_output[common_prefix_len:]

    #########################################################################
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

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
        for i in range(index):
            for arc in state.arcs:
                if arc.ilabel == inp[i]:
                    state = self._hypothesis[arc.nextstate]
                    s_index = arc.nextstate

        # The id of the state is its index inside the row list of the ot.
        access_string = self.ot.access_strings[s_index]
        logging.debug('Access string for index %d: %s - %d ',
                      index, access_string, s_index)
        return access_string


    def _check_suffix(self, inp, access_string, index):
        """
        Check if the suffixes produced by running the target machine in
        the strings access_string + inp[index:] and inp and check if the suffixes
        agree.

        Args:
            inp(list): string to check
            access_string(list): access_string for state to be tested.
            index (int): breakpoint in string inp

        Returns:
            True if strings disagree and False otherwise.
        """
        prefix_as = self.membership_query(access_string)
        full_as = self.membership_query(access_string + inp[index:])
        prefix_inp = self.membership_query(inp[:index])
        full_inp = self.membership_query(inp)
        common_prefix_len = len(commonprefix([prefix_as, full_as]))
        as_suffix = full_as[common_prefix_len:]
        common_prefix_len = len(commonprefix([prefix_inp, full_inp]))
        inp_suffix = full_inp[common_prefix_len:]
        return True if as_suffix != inp_suffix else False


    def _process_ce_rs(self, ce):
        """
        Counterexample processing using the adapted Rivest-Schapire algorithm.

        Args:
            ce (list): counterexample input
        """

        diff = len(ce)
        same = 0
        while True:
            i = (same + diff) / 2
            access_string = list(self._run_in_hypothesis(ce, i))
            is_diff = self._check_suffix(ce, access_string, i)
            if is_diff:
                diff = i
            else:
                same = i
            if diff-same == 1:
                break
        exp = tuple(ce[diff:])

        self.ot.dist_strings.append(exp)
        for row in self.ot.access_strings + self.ot.transitions:
            self._fill_ot_entry(row, exp)


    #########################################################################
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def _process_ce_sg(self, ce):
        """
        Counterexample processing using the Shabaz-Groz algorithm.

        Args:
            ce (list): counterexample input
        """

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


    #########################################################################
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

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
            self.ot.transitions.append(escaping_str + (i, ))
            for dist in self.ot.dist_strings:
                self._fill_ot_entry(escaping_str + (i, ), dist)

    def _construct_hypothesis(self):
        """
        Utilize the observation table to construct a Mealy Machine.

        Returns:
            Transducer: A mealy machine build based on a closed and consistent
            observation table.
        """
        mm = Transducer()
        for access_string in self.ot.access_strings:
            for i in self.I:
                dst = self.ot.equiv_classes[access_string + (i,)]
                # If dst == None then the table is not closed.
                if dst is None:
                    logging.debug('Conjecture attempt on non closed table.')
                    return None
                out = self.ot[access_string, (i, )]
                src_id = self.ot.access_strings.index(access_string)
                dst_id = self.ot.access_strings.index(dst)
                if not self.ot[access_string, (i, )]:
                    out = [EPSILON]
                else:
                    out = [int(x) for x in self.ot[access_string, (i, )]]
                mm.add_arc(src_id, dst_id, [int(i)], out)

        # This is for format compatibility with the DFA/SFAs.
        for state in mm.states:
            state.final = True
        return mm


    def _init_ot(self):
        """
        Initialize the observation table.
        """
        self.ot.access_strings.append(())
        self.ot.transitions = [(x, ) for x in list(self.I)]
        self.ot.dist_strings = [(x, ) for x in list(self.I)]
        for i in self.ot.dist_strings:
            self._fill_ot_entry((), i)
        for trans, dist in product(self.ot.transitions, self.ot.dist_strings):
            self._fill_ot_entry(trans, dist)


    def learn_mealy_machine(self):
        """
        Implements the high level loop of the algorithm for learning a
        Mealy machine.

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
            self.process_counterexample(ce)

        logging.info('Learning complete.')
        return self._hypothesis


if __name__ == '__main__':
    print 'Angluin Algorithm for learning Mealy Machines abstract' + \
            ' class implementation.'
