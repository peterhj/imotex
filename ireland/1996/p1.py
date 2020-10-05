from imomath import factorial, gcd, integer, positive
from imomath import a, Find, Let, Problem, Symbol

n = Symbol('n')
problem = Problem(
  Let(n).be(a(positive(integer))),
  Find(gcd(factorial(n)+1, factorial(n+1)))
)
print(problem)

