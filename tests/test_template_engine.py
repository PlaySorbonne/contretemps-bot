
from template import parser, Engine

ctx = { 'mouais': str, 'x':[1], 'y':lambda : 5, 'l':[(True,'gnee'), (False, 'gnoo')], 'none':None, 'lt':lambda a,b:a<b}
e = Engine(ctx)


res = parser.parse(
'{%if none%}  5 {%else%} 0 1 {%endif%}')
print(e.visit(res))

print(e.visit(parser.parse('{%if none%} BAD. {%endif%}')))

res = parser.parse('{%foreach (a,b) in l%} {{b}}!! {%if a%}hehe{%else%}hoho{%endif%}\n {%endfor%}')
print(e.visit(res))

res = parser.parse('{{y()}}{{y}} dfihfosihfghfg {%if1%}AAA{%else%}BBB{%endif%}')
print(e.visit(res))

res = parser.parse('{{[1,2, "hehe", [3]]}}')
print(e.visit(res))

res = parser.parse('{%let z = 16%} {{z}} {{z}}')
print(e.visit(res))

res = parser.parse(open('./src/ressources/default_task_main.template').read())

t = """{% if 0 %}{{1}}{{2}} {% endif %}"""
res = parser.parse(t)
print(e.visit(res))

res = parser.parse('{%foreach e in [1]%}gneu {{e}}gnee{%endfor%}DONEIT')
print(e.visit(res))

res = parser.parse('[{%foreach e in [1,2,3,4,5] with sep ", "%}{{e}}{%endfor%}]')
print(e.visit(res))

res = parser.parse('{%if any x in [1,1,1] where lt(10,x)%}hehe{%else%}hoho{%endif%}')
print(e.visit(res))

"""
delete from task;; delete from project ;; delete from task_step ;; delete from contributor ;; delete from task_veteran ;; delete from task_participant ;; delete from task_interested ;; delete from task_dependency ;; delete from project_alert ;; delete from task_log;;
"""
