"""Apply pinned textual source patches without requiring a system Git installation."""
from pathlib import Path, PurePosixPath
import re


def apply_patch(root, text, newline_override=None):
    root=Path(root).resolve()
    patch_newline="\r\n" if "\r\n" in text else "\n"
    lines=text.replace("\r\n","\n").splitlines(keepends=True)
    changes=[];i=0
    while i<len(lines):
        if not lines[i].startswith("--- "):
            i+=1;continue
        old_name=lines[i][4:].strip();i+=1
        if i>=len(lines) or not lines[i].startswith("+++ "):
            raise ValueError("Missing patch destination")
        new_name=lines[i][4:].strip();i+=1
        chosen=old_name if new_name=="/dev/null" else new_name
        if not chosen.startswith(("a/","b/")):
            raise ValueError("Unexpected source patch path")
        name=chosen[2:];relative=PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
            raise ValueError("Unsafe source patch path")
        target=root/name
        if not target.resolve().is_relative_to(root) or target.is_symlink():
            raise ValueError("Linked source patch target")
        if old_name!="/dev/null" and old_name[2:]!=name:
            raise ValueError("Renaming source patches is not supported")
        original_data="" if old_name=="/dev/null" else target.read_bytes().decode("utf-8")
        newline=("\r\n" if "\r\n" in original_data else "\n") if original_data else patch_newline
        newline=newline_override or newline
        original=original_data.replace("\r\n","\n").splitlines(keepends=True)
        output=[];cursor=0;hunks=0
        while i<len(lines) and not lines[i].startswith(("diff --git ","--- ")):
            match=re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@",lines[i])
            if not match:
                i+=1;continue
            expected=max(0,int(match[1])-1);old_count=int(match[2] or 1);new_count=int(match[4] or 1)
            i+=1;before=[];after=[];previous=None
            while i<len(lines) and (len(before)<old_count or len(after)<new_count):
                row=lines[i];i+=1
                if row.startswith("\\ No newline"):
                    if previous in (" ","-"):before[-1]=before[-1].removesuffix("\n")
                    if previous in (" ","+"):after[-1]=after[-1].removesuffix("\n")
                    continue
                if not row or row[0] not in " +-":
                    raise ValueError("Invalid source patch hunk")
                previous=row[0]
                if previous in " -":before.append(row[1:])
                if previous in " +":after.append(row[1:])
            if i<len(lines) and lines[i].startswith("\\ No newline"):
                if previous in (" ","-"):before[-1]=before[-1].removesuffix("\n")
                if previous in (" ","+"):after[-1]=after[-1].removesuffix("\n")
                i+=1
            if len(before)!=old_count or len(after)!=new_count:
                raise ValueError("Source patch hunk count mismatch")
            location=expected
            if location<cursor or original[location:location+old_count]!=before:
                locations=[index for index in range(cursor,len(original)-old_count+1)
                           if original[index:index+old_count]==before]
                if len(locations)!=1:
                    raise ValueError("Pinned patch context differs: "+name)
                location=locations[0]
            output.extend(original[cursor:location]);output.extend(after);cursor=location+old_count;hunks+=1
        if not hunks:
            raise ValueError("Source patch contains no textual hunks")
        output.extend(original[cursor:])
        changes.append((target,None if new_name=="/dev/null" else "".join(output).replace("\n",newline)))
    if not changes:
        raise ValueError("No source patches found")
    # All contexts and paths are checked before any source is changed.
    for target,value in changes:
        if value is None:target.unlink()
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            temporary=target.with_name(target.name+".patching")
            temporary.write_text(value,encoding="utf-8",newline="")
            temporary.replace(target)
