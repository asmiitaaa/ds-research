cpdef unsigned long long base26_encode(bytes s):
    cdef unsigned long long x = 0
    cdef Py_ssize_t i, n = len(s)

    for i in range(n):
        x = x * 26 + (s[i] - 97)

    return x
