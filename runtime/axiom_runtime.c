#include <stdlib.h>

_Noreturn void axiom_panic_i32(int code) {
    _Exit(code);
}
