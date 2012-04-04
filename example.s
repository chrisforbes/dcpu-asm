; example input
            set a, b
            set a, 0xbeef       ; test test
            set c, [a]          ; mem reference
            set [i], [j]        ; mem-to-mem ops, but this is dumb
            set [sp], [0x8000+i]  ;
            jsr global
.local:     sub pc, 1           ; loop here forever
.data:      dat "Hello World", 0
global:           ; just a label by itself

:crapstyle  dat "Blah labels are supported too", 0
