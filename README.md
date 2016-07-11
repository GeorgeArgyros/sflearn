## sflearn

**sflearn** is a small library implementing algorithms for inference of
deterministic transducers models. These models also include transducers with the
_bounded lookahead property_, i.e. transducers which consume more than one input
symbols with a single transition. These models are necessary in order to
represent programs such as string sanitizers. The library also contains a class
to convert the infered models into BEK programs (see the [BEK
tutorial](www.rise4fun.com/Bek/tutorial)).

The primary target of these algorithms are the inference of string manipulating
programs such as HTML encoders/decoders and filters used to sanitize untrusted
user input.

For more details, see the paper:
**Back in Black: Towards Formal, Black-Box Analysis of Sanitizers and Filters**
    _George Argyros, Ioannis Stais, Angelos D. Keromytis and Aggelos Kiayias_


## Requirements


## Installation


## Usage

In order to use this library one should inherit one of the learning algorithm
classes, either MealyMachineLearner, or TransducerLearner  and define the
methods membership\_query and equivalence\_query. For more details regarding
the logic of these methods consult the paper.

The examples/ directory contains a number of practical examples on how to use
these functions to construct models of various kinds of string manipulating
programs.


## Authors

The implementation of this library was designed and developed by George Argyros
and is based on the algorithms developed by George Argyros, Ioannis Stais,
Angelos D. Keromytis and Aggelos Kiayias.