
from template import parser, Engine

ctx = { 'mouais': [str], 'x':[1], 'y':[lambda : 5], 'l':[[(True,'gnee'), (False, 'gnoo')]]}
res = parser.parse('{{y()}}{{y}} dfihfosihfghfg {%if1%}AAA{%else%}BBB{%endif%}')
res = parser.parse('{%foreach (a,b) in l%} { {{b}}!! {%if a%}hehe{%else%}hoho{%endif%}\n }')
e = Engine(ctx)
print(e.visit(res))
