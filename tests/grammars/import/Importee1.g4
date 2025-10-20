/*
 * Copyright (c) 2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/* This grammar is used by ../Importer.g4 */

grammar Importee1;

import Importee3;

start: Token1 Token2 Token3;

Token1: 'a';  // overrides Importee3.Token1
// inherits Importee3.Token2
Token3: 'x';  // adds Token3
