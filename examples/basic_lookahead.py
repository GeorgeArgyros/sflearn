"""
This file provides a basic example of the learning algorithm for transducers
with bounded lookahead.

For details on the inference algorithm see the paper
* Back in Black: Towards Formal, Black-Box Analysis of Sanitizers and Filters
    George Argyros, Ioannis Stais, Angelos D. Keromytis and Aggelos Kiayias
"""
import argparse
import random


# Importing from ./context.py is performed to avoid assumptions on the location
# of the library on the system. If library is installed then `import sflearn`
# can be used.
from context import Transducer, TransducerLearner, BekProgram

class BasicLookaheadLearner(TransducerLearner):
    """
    This class implements a basic learning example for a transducer with
    bounded lookahead. The target transducer is an instance of the Transducer()
    class so it is easy to obtain ground truth and debug problem in the learning
    process.
    """

    def __init__(self, I):

        super(BasicLookaheadLearner, self).__init__(I)

        # This machine simulates idempotent encoders which avoid to encode
        # certain strings while encoding individual symbols.
        self.target = Transducer()
        self.target.add_arc(0, 0, [1], [1])
        self.target.add_arc(0, 0, [0], [0, 1, 1])
        self.target.add_arc(0, 0, [2], [2])
        self.target.add_arc(0, 0, [3], [3])
        self.target.add_arc(0, 0, [0, 1, 1], [0, 1, 1])
        self.target.add_arc(0, 0, [0, 2, 2], [0, 2, 2])
        self.target.add_arc(0, 0, [0, 3, 3], [0, 3, 3])


    def membership_query(self, inp):
        """
        Return the output from the target transducer on input inp.
        """
        return self.target.consume_input(inp)

    def equivalence_query(self, M):
        """
        Run the sanitizer on a bunch of random inputs and declare it correct
        if no counterexample is found.
        """
        max_len = 10
        tests_num = 1000
        for _ in xrange(tests_num):
            inp = []
            for _ in xrange(max_len):
                inp += [random.choice(self.I)]
            if M.consume_input(inp) != self.membership_query(inp):
                return False, inp
        return True, None



def _create_argument_parser():
    parser = argparse.ArgumentParser("")
    parser.add_argument("-o", "--out", default="basic_transducer", dest="outfile",
                        help="Filename to save the transducer")
    parser.add_argument("--bek", default=False, action="store_true", dest="save_bek",
                        help="Save transducer in BEK program format")
    return parser


def main():
    parser = _create_argument_parser()
    args = parser.parse_args()

    I = [0, 1, 2, 3]

    basic_lookahead_learner = BasicLookaheadLearner(I)
    print '[+] Learning transducer: ',
    sanitizer = basic_lookahead_learner.learn_transducer()
    print 'OK'

    print '[+] Saving transducer model in file {}.txt: '.format(args.outfile),
    sanitizer.save(args.outfile + '.txt')
    print 'OK'

    if args.save_bek:
        print '[+] Saving BEK program in file {}.bek: '.format(args.outfile),
        bek = BekProgram()
        bek.create_from_transducer(sanitizer)
        bek.save(args.outfile + '.bek')
        print 'OK'


if __name__ == '__main__':
    main()
