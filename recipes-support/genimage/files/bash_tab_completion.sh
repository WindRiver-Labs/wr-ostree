if [ -z $BASH_VERSION ]; then
    echo "Only bash support argcomplete"
    return
fi
eval "$(register-python-argcomplete appsdk)"
eval "$(register-python-argcomplete geninitramfs)"
eval "$(register-python-argcomplete genimage)"
eval "$(register-python-argcomplete genyaml)"
eval "$(register-python-argcomplete exampleyamls)"
eval "$(register-python-argcomplete gencontainer)"
