/*
 * Copyright (c) 2023 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

lexer grammar UnicodePropertiesLexer;

UPROP : [\p{Lu}] ;
GENERAL : [\p{General_Category=Other_Letter}] ;
ENUM_BLOCK : [\p{Blk=Latin_1_Sup}] [\p{Block=Latin_1_Supplement}] [\p{InLatin_1_Supplement}] [\p{InYijing_Hexagram_Symbols}] [\p{InAncient_Greek_Numbers}] ;
ENUM_SCRIPT : [\p{Script=Latin}] [\p{Script=Cyrillic}] -> mode(InvertedMode);

mode InvertedMode;
INVERTED : [\P{Latin}] -> mode(ExtrasMode);

mode ExtrasMode;
EXTRAS : [\p{EmojiPresentation=EmojiDefault}] [\p{EmojiPresentation=TextDefault}] [\p{EmojiPresentation=Text}] [\p{EmojiRK}] [\p{Extended_Pictographic}] -> mode(InvertedExtrasMode) ;

mode InvertedExtrasMode;
INVERTED_EXTRAS : [\P{Extended_Pictographic}] [\P{EmojiRK}] -> mode(InvertedExtrasMode);
