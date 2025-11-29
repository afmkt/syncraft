from __future__ import annotations
from typing import Any, Optional
from pyDatalog import pyDatalog as p, Logic

class Employee(p.Mixin):
    def __init__(self, name: str, manager: Optional[Employee], salary: float):
        super().__init__()
        self.name = name
        self.manager = manager
        self.salary = salary
    
John = Employee('John', None, 6800)

Mary = Employee('Mary', John, 6300)

Sam = Employee('Sam', Mary, 5900)

p.create_terms('X, Y, has_car')

print(X==1)


print((X == True) & (Y==False))

print((X==input('Please enter your name : ')) & (Y=='Hello ' + X[0]))
