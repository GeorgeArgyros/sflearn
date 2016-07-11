#!/usr/bin/env python
"""
Example usage for the LearnTransducer class. The algorithm is used to infer
a sample python implementation of the ReplaceComments() function used by
Mod-Security to deobfuscate inputs before they are passed through SQL injection
filters.

For details on the inference algorithm see the paper
* Back in Black: Towards Formal, Black-Box Analysis of Sanitizers and Filters
    George Argyros, Ioannis Stais, Angelos D. Keromytis and Aggelos Kiayias
"""
import argparse
import random

# Importing from ./context.py is performed to avoid assumptions on the location
# of the library on the system. If library is installed then `import sflearn`
# can be used.
from context import BekProgram, TransducerLearner

def replace_comments(inp):
    """""
    Sample implementation of the ReplaceComments function from Mod-Security.

    The function will remove all strings matching the /* */ style comments
    and replace them with a space.

    See function msre_fn_replaceComments_execute in the Mod-Security source
    code.
    """
    state = 0
    out = ''
    i = 0
    while i < len(inp):
        if state == 0 and inp[i:i+2] == "/*":
            i += 2
            state = 1
            out += ' '
            continue
        if state == 1 and inp[i:i+2] == "*/":
            i += 2
            state = 0
            continue

        if state == 0:
            out += inp[i]
            i += 1
        elif state == 1:
            i += 1
    return out


class ReplaceCommentsLearner(TransducerLearner):

    """
    The class implements membership and equivalence queries for the
    ReplaceComments() function.
    """

    def __init__(self, I):
        super(ReplaceCommentsLearner, self).__init__(I)


    def membership_query(self, inp):
        """
        Convert the input back to a string and run it through the encoder.
        """
        inp_enc = [chr(c) for c in inp]
        out = replace_comments(''.join(inp_enc))
        return [ord(c) for c in out]


    def equivalence_query(self, M):
        """
        Run the sanitizer on a bunch of random inputs and declare it correct
        if no counterexample is found.
        """
        tests = ['////*aaaaaa*/', '/*aaaaa*/', '*/aaaaa', 'aaaaaa/*aaaaaa']
        # Mix tests together with random strings
        max_len = 10
        tests_num = 100
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


def _create_argument_parser():
    parser = argparse.ArgumentParser("")
    parser.add_argument("-o", "--out", default="replacecomments", dest="outfile",
                        help="Filename to save the transducer")
    parser.add_argument("--bek", default=False, action="store_true", dest="save_bek",
                        help="Save transducer in BEK program format")
    return parser


def main():
    parser = _create_argument_parser()
    args = parser.parse_args()

    I = [ord(c) for c in set([x for x in '/**/abc'])]

    replace_comments_learner = ReplaceCommentsLearner(I)
    print '[+] Learning ReplaceComments() function: ',
    sanitizer = replace_comments_learner.learn_transducer()
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
