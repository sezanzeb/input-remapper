# Injection

This folder contains all classes that are only relevant for the injection
process. There is one process for each device that is being injected for,
and one context object that is being passed around everywhere for all to use.

The benefit of the context object over regular parameters is that the same
parameters don't have to be passed to classes and stored redundantly all
the time. The context is like the processes global configuration and you
can use whatever is inside. Just don't modify it. If you access a context
member in two classes you definitely know that those two are working with
the same thing without having to rely on scattering your pointers everywhere.
