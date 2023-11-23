/*
 * Copyright (c) 2024 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether the parser utility of Grammarinator creates
 * the same tree structures as generator would do.
 */

grammar Parse;

start
  : element (' ' element)*    # Quantifiers_test
  | element (' | ' element)+  # Quantifiers_test
  | list_with_recursion       # Recursion_test
  ;

element
  : 'pass' ('?' | '!')?
  ;

list_with_recursion
  : list_with_recursion (', ' element)
  | element
  ;
