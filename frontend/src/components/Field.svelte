<!-- Input with a label above it. <Field label="Name"><input class="input" …></Field>
     The label names the content as a group (screen readers announce it when entering the field). -->
<script>
  let { label = '', class: cls = '', children } = $props()
  const uid = $props.id()
</script>

<div class="field {cls}" role={label ? 'group' : undefined} aria-labelledby={label ? `${uid}-label` : undefined}>
  {#if label}<span class="lbl" id="{uid}-label">{label}</span>{/if}
  {@render children?.()}
</div>
