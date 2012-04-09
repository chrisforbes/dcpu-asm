; example input
            set a, b
            set a, 0xbeef       ; test test
            set c, [a]          ; mem reference
            set [i], [j]        ; mem-to-mem ops, but this is dumb
            set [sp], [0x8000+i]  ;
            jsr do_stuff
.local:     sub pc, 1           ; loop here forever
.data:      dat "Hello World", 0
do_stuff:   add a, 1
            jmp .enddo
            jmp do_stuff
.enddo:	    ret

:crapstyle  dat "Blah labels are supported too", 0

            def video, 0x8000
            def keyboard, 0x9000
