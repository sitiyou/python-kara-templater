project(
    'kara-templater-native', 'c', 'cpp',
    meson_version: '>=1.3',
    default_options: ['buildtype=release', 'default_library=static', 'cpp_std=c++17'],
)

python = import('python').find_installation(get_option('python'))
python.extension_module('_text_native', 'metrics.cpp', dependencies: [
    dependency('freetype2'), dependency('harfbuzz'), dependency('fribidi'), dependency('fontconfig'),
])
