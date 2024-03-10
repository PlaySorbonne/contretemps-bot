# This file is part of ContretempsBot <https://github.com/PlaySorbonne/contretemps-bot>
# Copyright (C) 2023-present PLAY SORBONNE UNIVERSITE
# Copyright (C) 2023 DaBlumer
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
- Small generic template language and renderer.
- Should allow to refer to attributes, do simple loops on iterables and call
arbitrary user functions, and nothing more.
- The rationale is that this is to be used as a minimal <message formating tool>
generator, and in the meantime allow a user of the generator to specify more
advanced semantic meanings to a <formating tool> instance by way of functions.
  --> For example, one can generate a tool that allows formatting discord
      messages while having access to a specific calendar's event as attributes.
      And one can also generate a generic tool that makes discord messages but
      while having access to a rich set of formatting functions.
      And by way of closure lambdas, one can make a tool that allows its users to
      specify some options to the code that will receive the generated text : one
      example of that is to add a directive like function that specifies
      some picture
      to join to the discord message.
"""

from lark import Lark, Token
from lark.visitors import Interpreter

template_grammar = r"""
    // Grammar
    start: _block*
    _block: text
          | value
          | foreach
          | ifelse
          | let
    value: _OPEN_VAL _expr _CLOSE_VAL
    _expr: _atomic | app | list
    _atomic: estring | number | id
    app: _expr _LPAR (_expr (_COMMA _expr)*)? _RPAR
    list: _LB (_expr (_COMMA _expr)*)? _RB
    ifelse: _OPEN_DIR _IF _expr _CLOSE_DIR _FORDELIM _block+ _ENDFORDELIM [else2_] _endif
           |_OPEN_DIR _IF _expr _CLOSE_DIR text [else_] _endif
    else_: _OPEN_DIR _ELSE _CLOSE_DIR text
    else2_: _OPEN_DIR _ELSE _CLOSE_DIR _FORDELIM _block+ _ENDFORDELIM
    foreach: _OPEN_DIR _FOREACH id_tuple _IN _expr _CLOSE_DIR _FORDELIM [start] _ENDFORDELIM
    let: _OPEN_DIR _LET ID _EQ _expr _CLOSE_DIR
    _endif: _OPEN_DIR _ENDIF _CLOSE_DIR
    id_tuple: _LPAR ID (_COMMA ID)* _RPAR | ID
    text: LETTER+
    id: ID
    number: NUMBER
    estring: ESCAPED_STRING
    
    //Lexing
    %import common.NUMBER
    %import common.ESCAPED_STRING
    %import common.WS
    _OPEN_VAL.2: "{{" WS*
    _CLOSE_VAL: WS* "}}"
    _OPEN_DIR.2: "{%" WS*
    _CLOSE_DIR: WS* "%}" "\n"?
    _COMMA: WS* "," WS*
    _IF: WS* "if"i WS*
    _ELSE: WS* "else"i WS*
    _ENDIF: WS* "endif"i WS*
    _ENDFOR: WS* "endfor"i WS*
    _FOREACH: WS* "foreach"i WS*
    _LET.2: WS? "let"i WS?
    _EQ: WS? "=" WS?
    _LPAR: WS* "(" WS*
    _RPAR: WS* ")" WS*
    _LB: WS* "[" WS*
    _RB: WS* "]" WS*
    _IN: WS* "in"i WS*
    ID: /[a-zA-Z_][a-zA-Z0-9_]*/
    LETTER.-1: /./s
    _FORDELIM: "{" WS*
    _ENDFORDELIM: "}" ("\n"|" ")?
"""

class LvlDict:
  """
  Allows for efficient handling of evaluation contexts without copying
  and without relying on the structure of the used dictionnary-like object.
  """
  def __init__(self, old, add):
    self.old = old
    self.add = add
  
  def __getitem__(self, o):
    if o in self.add : return self.add[o]
    return self.old[o]
  
  def __contains__(self, o):
    o in add or o in old

class Engine(Interpreter):
  
  def __init__(self, context, *args, **kwargs): #TODO typing, error handling (both communicating position of bad in parsing and handling errors here)
    self.stack = [context]
    super().__init__(*args, **kwargs)
  
  text = lambda self, s : ''.join(k[0] for k in s.children)
  
  def start(self, tree):
    return ''.join(str(e) for e in self.visit_children(tree))
  
  def ifelse(self, items):
    items = items.children
    if self.visit(items[0]):
      return ''.join(str(self.visit(i)) for i in items[1:-1])
    return self.visit(items[-1]) if items[-1] else ""
  
  def else_(self, tree):
    t = tree.children[0]
    return self.visit(t) if t else ""
  
  def value(self, tree):
    return self.visit(tree.children[0])
  
  def app(self, tree):
    f = self.visit(tree.children[0])
    to = (self.visit(i) for i in tree.children[1:])
    return f(*to)
  
  def list(self, tree):
    return [self.visit(child) for child in tree.children]
  
  def foreach(self, tree):
    ids = self.visit(tree.children[0])
    loop_over = self.visit(tree.children[1])
    if not tree.children[2]: return ""
    res = []
    n = len(ids)
    for T in loop_over:
      assert n == 1 or len(T) == n
      new = {ids[i] : T[i] for i in range(n)} if n > 1 else {ids[0]:T}
      self.stack.append(LvlDict(self.stack[-1], new))
      res.append(self.visit(tree.children[2]))
      self.stack.pop()
    return ''.join(res)
  
  def let(self, tree):
    new_id = tree.children[0][:]
    value = self.visit(tree.children[1])
    self.stack.append(LvlDict(self.stack[-1], {new_id:value}))
    return ''
  
  def id_tuple(self, tree):
    return [u[:] for u in self.visit_children(tree)]
      
  
  def number(self, n):
    try:
      return int(n.children[0])
    except Exception:
      return float(n.children[0])
  def estring(self, s):
    return s.children[0][1:-1]
  def id(self, tree):
    ctx = self.stack[-1]
    return ctx[tree.children[0][:]]
  


parser = Lark(template_grammar, parser='lalr')
