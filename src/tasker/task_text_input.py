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
Parser module allowing to parse a textual presentation of a list of
tasks and transforming it to a list of database.tasker.Task object
"""
from database.tasker import Task, TaskStep, TaskLog, TaskDependency
from lark import Lark, Transformer

tasks_grammar = r"""
    // Grammar
    start: task*
    task: _NEW task_element+
    ?task_element: title | ref | description | startdate | enddate
                  | beforedate | steps | dependencies
    title: _TITLE basic_text
    ref: _REF basic_text
    description: _DSC basic_text
    startdate: _SD basic_text
    enddate: _ED basic_text
    beforedate: _MSB basic_text
    steps: _STPS _TEXT_START (step)* _TEXT_END
    ?step: subtask | remark
    subtask: _SBTSK _LPAR NUMBER _RPAR basic_text
    remark : _PS basic_text
    dependencies: _DPDN _TEXT_START dependency* _TEXT_END
    ?dependency: basic_text
    ?basic_text: _TEXT_START text _TEXT_END
    text: TEXT?
    
    
    
    // Terminals
    COL: ":"
    _TEXT_START: /<<(\n)*/
    _TEXT_END: /(\n)*>>/
    TEXT: /((?!>>)(?!<<).)+/s
    _NEW: "NewTask."i
    _TITLE: "Title"i
    _REF: "ref"i
    _DSC: "description"i
    _SD: "startDate"i
    _ED: "endDate"i
    _MSB: "muststartbefore"i
    _STPS: "steps"i
    _DPDN: "dependencies"i
    _SBTSK: "subtask"i
    _PS: "ps"i
    _LPAR: "("
    _RPAR: ")"
    %import common.NUMBER
    
    %import common.WS
    %ignore WS
"""

class TaskMaker(Transformer):
    text = lambda self, s : s[0][:].strip(' ')
    title = lambda self, items : ("title", items[0].strip(' '))
    description = lambda self, items : ("description", items[0].strip(' '))
    ref = lambda self, items : ("ref", items[0].strip(' '))
    subtask = lambda self, items : (TaskStep.SUBTASK,float(items[0][:]),items[1])
    remark = lambda self, items : (TaskStep.REMARK, None, items[0].strip(' '))
    startdate = lambda self, items : ("starts_after", items[0].strip())
    enddate = lambda self, items : ("ends_before", items[0].strip())
    beforedate = lambda self, items : ("urgent_after", items[0].strip())
    dependency = lambda self, items : items[0]
    
    def steps(self, items):
      return ('steps',[TaskStep(kind=k, step_number=n, step_description=s.strip(' '))
                       for (k,n,s) in items])
    def dependencies(self, items):
      return ("deps", items)
    
    def task(self, items):
      ref, deps, steps, attrs = None, [], [], dict()
      for (what, itm) in items:
        if what == 'ref': ref = itm
        elif what == 'deps': deps = itm
        elif what == 'steps': steps = itm
        else: attrs[what] = itm
      new_task = Task(**attrs)
      new_task.steps = steps
      if ref is None: ref = attrs['title'] #TODO : check title exists for all tasks and emit useful error message to user
      return (new_task, ref, deps)
    
    def start(self, items):
      tasks = dict()
      for (new_task, ref, deps) in items:
        tasks[ref] = new_task
      for (new_task, _, deps) in items:
        for dep in deps:
          if dep in tasks:
            tasks[dep].successors.append(new_task)
      return tasks.values()
    

tasks_parser = Lark(tasks_grammar, transformer=TaskMaker(), parser='lalr')
