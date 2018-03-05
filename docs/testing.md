Setting up testing
==================

TravisCI
--------

The repository at github.com/TACC/agave-files is already configured for 
testing with a service account. To set TravisCI testing up in a fork, with
your own credentials, you need to create the following variables:

```shell
travis encrypt _AGAVE_USERNAME=user_name --add
travis encrypt _AGAVE_PASSWORD=password --add
travis encrypt _AGAVE_APIKEY=consumer_key --add
travis encrypt _AGAVE_APISECRET=consumer_secret --add
travis encrypt _AGAVE_CLIENT_NAME=client_name --add
```

:star: If you define a variable with the same name in .travis.yml and in the 
Repository Settings, the one in .travis.yml takes precedence. If you define 
a variable in .travis.yml as both encrypted and unencrypted, the one defined 
later in the file takes precedence. (Source: [Travis-CI docs][1])

[1]: https://docs.travis-ci.com/user/environment-variables/#Defining-public-variables-in-.travis.yml
