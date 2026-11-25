use std::env;
use std::io::{self, Read};
use std::process::ExitCode;

use naga::back::glsl::{Options, PipelineOptions, Version, Writer};
use naga::valid::{Capabilities, ShaderStages, ValidationFlags, Validator};
use naga::{ShaderStage, TypeInner};

const FRAGMENT: &str = "kara_compile_fragment";
const EFFECT: &str = "kara_compile_paint";
const CONTEXT: &str = "KaraPaintContext";

fn compile(source: &str, namespace: &str) -> Result<String, String> {
    let mut module =
        naga::front::wgsl::parse_str(source).map_err(|err| err.emit_to_string(source))?;
    if module.entry_points.len() != 1 || module.entry_points[0].name != FRAGMENT {
        return Err("effect modules may only declare ordinary functions".into());
    }
    if !module.global_variables.is_empty() || !module.overrides.is_empty() {
        return Err(
            "effect modules receive resources and parameters through their arguments".into(),
        );
    }
    let effect = module
        .functions
        .iter()
        .find_map(|(handle, f)| (f.name.as_deref() == Some(EFFECT)).then_some(handle))
        .ok_or("missing generated material function")?;
    let info = Validator::new(ValidationFlags::all(), Capabilities::empty())
        .validate(&module)
        .map_err(|err| err.emit_to_string(source))?;
    if info[effect].may_kill
        || !info[effect]
            .available_stages
            .contains(ShaderStages::COMPUTE)
    {
        return Err("material functions may not discard pixels or use fragment derivatives".into());
    }

    for (_, f) in module.functions.iter_mut() {
        if let Some(name) = f.name.as_mut() {
            *name = format!("{namespace}_{name}");
        }
    }
    for (_, c) in module.constants.iter_mut() {
        if let Some(name) = c.name.as_mut() {
            *name = format!("{namespace}_{name}");
        }
    }
    let structs: Vec<_> = module
        .types
        .iter()
        .filter(|(_, ty)| matches!(ty.inner, TypeInner::Struct { .. }))
        .map(|(handle, ty)| (handle, ty.clone()))
        .collect();
    for (handle, mut ty) in structs {
        ty.name = Some(match ty.name {
            Some(name) => format!("{namespace}_{name}"),
            None => format!("{namespace}_type_{}", handle.index()),
        });
        module.types.replace(handle, ty);
    }

    let mut generated = String::new();
    Writer::new(
        &mut generated,
        &module,
        &info,
        &Options {
            version: Version::new_gles(300),
            ..Options::default()
        },
        &PipelineOptions {
            shader_stage: ShaderStage::Fragment,
            entry_point: FRAGMENT.into(),
            multiview: None,
        },
        Default::default(),
    )
    .and_then(|mut writer| writer.write())
    .map_err(|err| err.to_string())?;

    // The renderer owns the stage and framebuffer. Retain only the library
    // body from Naga's validated fragment entry and its ordinary functions.
    let body = generated
        .split_once("\nvoid main() {")
        .map(|(body, _)| body)
        .ok_or("unexpected GLSL fragment entry from Naga")?;
    if !body.contains(&format!("vec4 {namespace}_{EFFECT}("))
        || !body.contains(&format!("struct {namespace}_{CONTEXT} "))
    {
        return Err("unexpected material interface in generated GLSL".into());
    }
    let mut library = String::new();
    for line in body.lines() {
        match line {
            "#version 300 es"
            | "precision highp float;"
            | "precision highp int;"
            | "layout(location = 0) out vec4 _fs2p_location0;" => continue,
            _ if line.starts_with('#') || line.starts_with("layout(") => {
                return Err(format!("unsupported GLSL stage declaration: {line}"));
            }
            _ => {}
        }
        library.push_str(line);
        library.push('\n');
    }
    // Naga's math compatibility helpers are local to each generated module.
    for helper in ["naga_modf", "naga_frexp"] {
        library = library.replace(&format!("{helper}("), &format!("{namespace}_{helper}("));
    }
    Ok(library)
}

fn run() -> Result<(), String> {
    let namespace = env::args().nth(1).ok_or("missing shader namespace")?;
    if !namespace.starts_with("kara_effect_")
        || !namespace
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'_')
    {
        return Err("invalid shader namespace".into());
    }
    let mut source = String::new();
    io::stdin()
        .read_to_string(&mut source)
        .map_err(|err| err.to_string())?;
    print!("{}", compile(&source, &namespace)?);
    Ok(())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}
