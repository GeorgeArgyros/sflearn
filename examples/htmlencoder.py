#!/usr/bin/env python
"""
Infer the HTML encoder from cgi module in python using the learning algorithm
for Mealy Machines with epsilon transitions.

For details on the inference algorithm see the paper
* Back in Black: Towards Formal, Black-Box Analysis of Sanitizers and Filters
    George Argyros, Ioannis Stais, Angelos D. Keromytis and Aggelos Kiayias
"""

import argparse
import random
import string
from cgi import escape

from context import BekProgram, MealyMachineLearner

class EncoderLearner(MealyMachineLearner):

    """
    Implements the class to infer the HTML encoder from the cgi python module.
    membership and equivalence queries are implemented.
    """

    def membership_query(self, s):
        """
        Convert the input back to a string and run it through the encoder.
        """
        inp = ''.join([chr(c) for c in s])
        return [ord(c) for c in escape(inp)]


    def equivalence_query(self, M):
        """
        Run the sanitizer on a bunch of random inputs and declare it correct
        if no counterexample is found.
        """
        max_len = 15
        tests_num = 100
        tests = ['&gt;', '&lt;', '&quot;', '&apos;']
        for _ in xrange(tests_num):
            inp = []
            for _ in xrange(random.randint(1, max_len)):
                inp += [random.choice(self.I)]
                if random.randint(0, 10) == 5:
                    vector = random.choice(tests)
                    inp += [ord(c) for c in vector]
            if M.consume_input(inp) != self.membership_query(inp):
                return False, inp
        return True, None


def _create_argument_parser():
    parser = argparse.ArgumentParser("")
    parser.add_argument("-o", "--out", default="encoder", dest="outfile",
                        help="Filename to save the transducer")
    parser.add_argument("--bek", default=False, action="store_true", dest="save_bek",
                        help="Save transducer in BEK program format")
    return parser


def main():
    parser = _create_argument_parser()
    args = parser.parse_args()

    # Alphabet for the experiments
    I = [ord(x) for x in string.punctuation + string.lowercase]

    enc_learn = EncoderLearner(I)
    print '[+] Learning HTML Encoder: ',
    sanitizer = enc_learn.learn_mealy_machine()
    print 'OK'

    print '[+] Saving in file {}.[txt|bek]: '.format(args.outfile),
    sanitizer.save(args.outfile + '.txt')
    if args.save_bek:
        bek = BekProgram()
        bek.create_from_transducer(sanitizer)
        bek.save(args.outfile + '.bek')
    print 'OK'


if __name__ == '__main__':
    main()
