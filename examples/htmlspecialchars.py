#!/usr/bin/env python
"""
Example showing how to use the algorithm for inferring transducers with
bounded lookahead to learn a correct model of the htmlspecialchars() function
in PHP when the double_encode option is disabled.

Disabling this option will instruct the encoder not to re-encode already
encoded HTML entities. In order to achieve this, a number of lookahead
paths has to be added in the corresponding transducer.
"""
import argparse
import random
import subprocess

# Importing from ./context.py is performed to avoid assumptions on the location
# of the library on the system. If library is installed then `import sflearn`
# can be used.
from context import BekProgram, TransducerLearner

PHP_INPUT_FILE = 'input.pipe.txt'
PHP_ENCODER_FILE = './call_htmlspecialchars.php'

class HTMLSpecialCharsLearner(TransducerLearner):
    """
    The class implements a simple IPC in order to communicate with the PHP
    script executing the calls to the htmlspecialchars() function.
    """
    def __init__(self, I):

        super(HTMLSpecialCharsLearner, self).__init__(I)
        self.query_cache = {}
        self.total_membership_queries = 0
        self.total_equiv_queries = 0
        self.total_cached_queries = 0


    def membership_query(self, inp):
        """
        The input from a membership query is written into a file which is then
        read by the PHP script. The output of the htmlspecialchars() function
        is then written into stdout from where it is read into the python
        script.

        This class also implements a query cache to avoid making expensive calls
        IPC operations during membership queries.
        """

        self.total_membership_queries += 1

        if tuple(inp) in self.query_cache:
            self.total_cached_queries += 1
            return self.query_cache[tuple(inp)]

        inp_enc = [chr(c) for c in inp]
        with open(PHP_INPUT_FILE, 'w') as php_input_file:
            php_input_file.write(''.join(inp_enc))
        proc = subprocess.Popen("php {}".format(PHP_ENCODER_FILE),
                                shell=True, stdout=subprocess.PIPE)
        out = proc.stdout.read()
        dec_out = [ord(c) for c in out]
        self.query_cache[tuple(inp)] = dec_out
        return dec_out


    def equivalence_query(self, M):
        """
        Run the sanitizer on a bunch of random inputs and declare it correct
        if no counterexample is found.
        """
        self.total_equiv_queries += 1

        tests = ['&amp;', '&&amp;', '&a&amp;', '&am&amp;', '&amp&amp;']
        tests += ['&gt;', '&lt;', '&g&gt;', '&lt&lt;']

        # Mix them together in random strings
        max_len = 10
        tests_num = 150
        for _ in xrange(tests_num):
            inp = []
            for _ in xrange(max_len):
                inp += [random.choice(self.I)]
                if random.randint(0, 10) == 5:
                    vector = random.choice(tests)
                    inp += [ord(c) for c in vector]

            if M.consume_input(inp) != self.membership_query(inp):
                return False, inp
        return True, None


    def get_query_stats(self):
        """
        Return the statistics for the number of queries performed.
        """
        return (self.total_membership_queries, self.total_equiv_queries,\
                self.total_cached_queries)


def _create_argument_parser():
    parser = argparse.ArgumentParser("")
    parser.add_argument("-o", "--out", default="htmlspecialchars", dest="outfile",
                        help="Filename to save the transducer")
    parser.add_argument("--bek", default=False, action="store_true", dest="save_bek",
                        help="Save transducer in BEK program format")
    return parser


def main():
    parser = _create_argument_parser()
    args = parser.parse_args()

    I = [ord(c) for c in set([x for x in '&amp&lt;&gt;<>abcd'])]
    htmlspecialchars_learner = HTMLSpecialCharsLearner(I)
    print '[+] Learning PHP htmlspecialchars() function: ',
    htmlspecialchars = htmlspecialchars_learner.learn_transducer()
    print 'OK'


    (memb, equiv, cache) = htmlspecialchars_learner.get_query_stats()
    print '[+] Total number of membership queries: {}'.format(memb)
    print '[+] Total number of equivalence queries: {}'.format(equiv)
    print '[+] Total number of cached membership queries: {}'.format(cache)

    print '[+] Saving transducer model in file {}.txt: '.format(args.outfile),
    htmlspecialchars.save(args.outfile + '.txt')
    print 'OK'
    if args.save_bek:
        print '[+] Saving BEK program in file {}.bek'.format(args.outfile)
        bek = BekProgram()
        bek.create_from_transducer(htmlspecialchars)
        bek.save(args.outfile + '.bek')
        print 'OK'

if __name__ == '__main__':
    main()
