import sys
import warnings

class InterpreterError(Exception):
    def __init__(self, msg, line, char):
        self.msg = msg
        self.line = line
        self.char = char

    def __str__(self):
        return "%s (line %d, char %d)" % (self.msg, self.line, self.char)

def dereference(val, vars_, line, char):
    try:
        x = val
        # if x[0] != "ref":
        #     raise RuntimeError("Top of stack isn't a reference")
        y = vars_
        for i in x[1:-1]:
            y = y[i][1]

        return y[x[-1]]  # stack.append(y[x[-1]])
    except KeyError:
        raise InterpreterError("Dereferencing a non-existant field", line, char) from None

def GetNOffStack(n, stack, vars_, line, char, types=None, err_begin="Only accepting"):
    res = []
    for _ in range(n):
        x = stack.pop()
        if types:
            if x[0] not in types:
                if len(types) > 1:
                    accepting_what = ", ".join([i+"s" for i in types[:-1]]) + " and " + types[-1] + "s"
                else:
                    accepting_what = types[0] + "s"
                raise InterpreterError(err_begin + " " + accepting_what + ", not " + x[0] + "s!", line, char)
        res.append(x)
    return res

def tokenize(code):
    x = ""
    line = 0
    char = 1
    mode = "normal"
    ignore = 0
    for i in code:
        if mode == "normal":
            if i in ("\n", " "):
                yield line, char, x
                x = ""
            else:
                x += i
                if x == "\"":
                    mode = "string"
        elif mode == "string":
            x += i
            if i == "\"":
                if ignore:
                    ignore = 0
                else:
                    mode = "normal"
                    yield line, char, x
                    x = ""
            elif i == "\\":
                if ignore:
                    ignore = 0
                else:
                    ignore = 1
                    x = x[:-1]

        if i == "\n":
            line += 1
            char = 0
        char += 1
    char += 1
    yield line, char, x

def do_call(x, stack, vars_, line, char):
    if x[0] != "func":
        raise InterpreterError("Top of stack isn't a function", line, char)
    if type(x[2]) != str:
        args = []
        for _ in range(int(x[1][1])):
            tmp = stack.pop()
            if tmp[0] == "decimal":
                args.append(tmp[1])
            elif tmp[0] == "string":
                args.append(tmp[1])
            else:
                args.append(tmp)
        res = x[2](*args[::-1])
        if res is None:
            stack.append(("null",))
        elif type(res) in (int, float):
            stack.append(("decimal", res))
        elif type(res) == str:
            stack.append(("string", res))
        else:
            raise InterpreterError("Interpreter function returned type '%s', which cannot be translated." % (type(res)), line, char)
    else:
        if x[1][0] == "decimal":                              # yes a function
            args = []
            for _ in range(int(x[1][1])):
                args.append(stack.pop())
            res = interpreter(x[2], args)[0]
            if len(res) > 1:
                raise InterpreterError("Function didn't properly clean stack (resulting stack size > 1)", line, char)
            stack.append(res[0])
        elif x[1][0] == "null":                               # not a function
            res = interpreter(x[2], stack, vars_)
            stack, vars_ = res
        else:
            raise InterpreterError("Invalid type for arg size. (got '%s')" % (x[0], line, char))
    return stack, vars_

def do_operand_call(op, x, y, stack, vars_, line, char):
    if y[0] == "object" or x[0] == "object":
        if x[0] == "object":
            stack.append(x)
            stack.append(y)
            do_call(x[1][">"], stack, vars_, line, char)
            res = stack.pop()
            if res != ("null",):
                return res, stack, vars_
        if y[0] == "object":
            stack.append(x)
            stack.append(y)
            do_call(y[1][">"], stack, vars_, line, char)
            res = stack.pop()
            if res != ("null",):
                return res, stack, vars_
        
        raise InterpreterError("Could not '%s' objects" % (op), line, char)
    return None, stack, vars_

def interpreter(code, _stack=[], _vars={}):
    mode_stack = ["interpret",]
    vars_ = {
        "G": ("object", {}),
        "io": ("object", {
            "print": ("func", ("decimal", 1), print),
            "input": ("func", ("decimal", 1), input),
        })
    }
    vars_.update(_vars)
    stack = []
    stack += _stack[:]
    defd = ""
    n_of_args = None
    def_layers = 0
    # print("==== NEW INTERPRETER INSTANCE (start of file / function call / code block)")
    # print("line char token          stack                                                                                                 Current scope variables")
    for line, char, i in tokenize(code):
        # print("%4d %4d %15s %-100s %s" % (line, char, i, stack, vars_["G"][1]))
        if mode_stack[-1] == "interpret":
            if i == "":
                continue
            try:
                stack.append(("decimal", float(i)))
                continue
            except ValueError:
                pass
            if i == "_":
                stack.pop()   # Eat a value off the stack
            elif i == "|":
                # Exchange 2 top elements of the stack
                x = stack.pop()
                y = stack.pop()
                stack.append(x)
                stack.append(y)
            elif i == ">":
                if len(stack) < 2:
                    raise InterpreterError("Nothing left to pop off the stack", line, char)

                y, x = GetNOffStack(
                    2, stack, vars_, line, char,
                    types=("decimal", "object"),
                    err_begin="Can only compare"
                )

                res, stack, vars_ = do_operand_call(">", y, x, stack, vars_, line, char)
                if res:
                    stack.append(res)
                    continue
  
                stack.append(("decimal", int(x[1] > y[1])))
            elif i == "<":
                if len(stack) < 2:
                    raise InterpreterError("Nothing left to pop off the stack", line, char)

                y, x = GetNOffStack(
                    2, stack, vars_, line, char,
                    types=("decimal", "object"),
                    err_begin="Can only compare"
                )

                res, stack, vars_ = do_operand_call("<", y, x, stack, vars_, line, char)
                if res:
                    stack.append(res)
                    continue

                stack.append(("decimal", int(x[1] < y[1])))
            elif i == "==":
                if len(stack) < 2:
                    raise InterpreterError("Nothing left to pop off the stack", line, char)

                y, x = GetNOffStack(
                    2, stack, vars_, line, char,
                    types=("decimal", "string", "ref", "object"),
                    err_begin="Can only compare"
                )

                if y[0] != x[0]:
                    raise InterpreterError("Both values must be of the same type", line, char)

                res, stack, vars_ = do_operand_call("==", y, x, stack, vars_, line, char)
                if res:
                    stack.append(res)
                    continue

                stack.append(("decimal", int(x[1] == y[1])))
            elif i == "!=":
                if len(stack) < 2:
                    raise InterpreterError("Nothing left to pop off the stack", line, char)

                y, x = GetNOffStack(
                    2, stack, vars_, line, char,
                    types=("decimal", "string", "ref", "object"),
                    err_begin="Can only compare"
                )

                if y[0] != x[0]:
                    raise InterpreterError("Both values must be of the same type", line, char)

                re, stack, vars_s = do_operand_call("!=", y, x, stack, vars_, line, char)
                if res:
                    stack.append(res)
                    continue

                stack.append(("decimal", int(x[1] != y[1])))
            elif i == "?":
                # If
                yes = stack.pop()
                value = stack.pop()
                if value[0] == "string":
                    if len(value[1]) > 0:
                        stack, vars_ = do_call(yes, stack, vars_, line, char)
                elif value[0] == "decimal":
                    if value[1] != 0:
                        stack, vars_ = do_call(yes, stack, vars_, line, char)
                elif value[0] == "null":
                    pass   # Null is never true
                elif value[0] == "object":
                    if len(value[1]) > 0:
                        stack, vars_ = do_call(yes, stack, vars_, line, char)
                else:
                    raise InterpreterError("Type on top of stack cannot be turned into a boolean", line, char)
            elif i == "?:":
                # If else
                yes = stack.pop()
                no = stack.pop()
                value = stack.pop()
                if value[0] == "string":
                    if len(value[1]) > 0:
                        stack, vars_ = do_call(yes, stack, vars_, line, char)
                    else:
                        stack, vars_ = do_call(no, stack, vars_, line, char)
                elif value[0] == "decimal":
                    if value[1] != 0:
                        stack, vars_ = do_call(yes, stack, vars_, line, char)
                    else:
                        stack, vars_ = do_call(no, stack, vars_, line, char)
                elif value[0] == "null":
                    pass   # Null is never true
                elif value[0] == "object":
                    if len(value[1]) > 0:
                        stack, vars_ = do_call(yes, stack, vars_, line, char)
                    else:
                        stack, vars_ = do_call(no, stack, vars_, line, char)
                else:
                    raise InterpreterError("Type on top of stack cannot be turned into a boolean", line, char)
            elif i == "+":
                if len(stack) < 2:
                    raise InterpreterError("Nothing left to pop off the stack", line, char)

                y, x = GetNOffStack(
                    2, stack, vars_,
                    types=("decimal", ),
                    err_begin="Can only add"
                )

                stack.append(("decimal", x[1] + y[1]))
            elif i == "-":
                if len(stack) < 2:
                    raise InterpreterError("Nothing left to pop off the stack", line, char)
                
                y, x = GetNOffStack(
                    2, stack, vars_,
                    types=("decimal", ),
                    err_begin="Can only subtract"
                )
                
                stack.append(("decimal", x[1] - y[1]))
            elif i == "*":
                if len(stack) < 2:
                    raise InterpreterError("Nothing left to pop off the stack", line, char)
                
                y, x = GetNOffStack(
                    2, stack, vars_,
                    types=("decimal", ),
                    err_begin="Can only multiply"
                )
                
                stack.append(("decimal", x[1] * y[1]))
            elif i == "/":
                if len(stack) < 2:
                    raise InterpreterError("Nothing left to pop off the stack", line, char)
                
                y, x = GetNOffStack(
                    2, stack, vars_,
                    types=("decimal", ),
                    err_begin="Can only divide"
                )
                
                stack.append(("decimal", x[1] / y[1]))
            elif i.startswith("\""):
                stack.append(("string", i[1:-1]))
            # elif i == "_":
            #     x = ("string", "")
            #     res1 = []
            #     while x[0] == "string" and len(stack) > 0:
            #         res1.append(x[1])
            #         x = stack.pop()
            # 
            #     if x[0] != "string":
            #         stack.append(x)
            #     else:
            #         res1.append(x[1])
            #     stack.append(" ".join(reversed(res1)))
            elif i == "object":
                stack.append(("object", {}))
            elif i == "null":
                stack.append(("null", ))
            elif i == ".":
                x = stack.pop()
                y = stack.pop()
                if vars_[x[1]][0] != "object":
                    raise InterpreterError("Type mismatch (attempting to take attrib of non-object)", line, char)
                if x[0] not in ("ref", "string"):
                    raise InterpreterError("Argument to . must be either ref or string", line, char)
                elif y[0] not in ("ref", "string"):
                    raise InterpreterError("Argument to . must be either ref or string", line, char)
                stack.append(("ref",) + x[1:] + y[1:])
            elif i == "**":
                x = stack.pop()
                if x[0] != "ref":
                    raise InterpreterError("Top of stack isn't a reference", line, char)
                stack.append(dereference(x, vars_, line, char))
            elif i == "=":
                dest = stack.pop()
                src = stack.pop()
                y = vars_
                for i in dest[1:-1]:
                    y = y[i][1]

                y[dest[-1]] = src
            elif i == "{":
                mode_stack.append("define")
                defd=""
                n_of_args=stack.pop()
            elif i == "/*":
                mode_stack.append("comment")
            elif i == ":":
                what = stack.pop()
                stack, vars_ = do_call(what, stack, vars_, line, char)
            else:
                raise InterpreterError("Unknown token '%s'" % (i), line, char)
        elif mode_stack[-1] == "define":
            if i == "/*":
                mode_stack.append("comment")
            elif i == "{":
                def_layers += 1
                defd += i
                defd += " "
            elif i == "}":
                if def_layers == 0:
                    stack.append(("func", n_of_args, defd))
                    mode_stack.pop()
                else:
                    def_layers -= 1
                    defd += i
                    defd += " "
            else:
                defd += i
                defd += " "
        elif mode_stack[-1] == "comment":
            if i == "*/":
                mode_stack.pop()
    # print("====================================================================================================================")
    return stack, vars_

# '''1 2 + "print "io . ** :'''

if len(sys.argv) < 2:
    print("Type 'END' to end")
    x = ""
    y = ""
    while y != "END":
        x += y
        x += "\n"
        y = input("> ")
        
    interpreter(x)
elif len(sys.argv) == 2:
    with open(sys.argv[1]) as f:
        try:
            interpreter(f.read())
        except InterpreterError as e:
            print("Error!", str(e))
