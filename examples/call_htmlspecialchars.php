<?php

/*
 * Read a string from the input.pipe.txt file and pass it through the
 * htmlspecialchars function. When this function is called with the
 * double_encode, i.e. the last, argument set to false, it will not reencode
 * html entities which are already encoded, such as &amp;.
 * In order to model this function with transducers a number of lookahead paths
 * are required.
 *
 * This script is called from the php_idempotent.py file which infers a model of
 * the encoder.
 */
$file='./input.pipe.txt';
$s = htmlspecialchars(file_get_contents($file), ENT_NOQUOTES, "UTF-8", false);
echo $s

?>
