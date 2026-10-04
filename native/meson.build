project(
    'kara-templater-native', 'c', 'cpp',
    meson_version: '>=1.3',
    default_options: ['buildtype=release', 'default_library=static', 'cpp_std=c++17'],
)

libass = subproject(
    'libass-0.17.5',
    default_options: [
        'fontconfig=disabled',
        'coretext=disabled',
        'directwrite=enabled',
        'libunibreak=disabled',
        'test=disabled',
        'compare=disabled',
        'profile=disabled',
        'fuzz=disabled',
        'checkasm=disabled',
    ],
)

python = import('python').find_installation(get_option('python'))
python.extension_module('_metrics', 'metrics.cpp', dependencies: libass.get_variable('libass_dep'))
