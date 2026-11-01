(() => {
  const list = document.querySelector('[data-milestone-list]');
  if (!list) return;
  const prefix = list.dataset.prefix;
  const max = Number(list.dataset.max || 8);
  const totalInput = document.querySelector(`#id_${prefix}-TOTAL_FORMS`);
  const addButton = document.querySelector('[data-add-milestone]');
  const emptyTemplate = document.querySelector('[data-empty-milestone]');
  const totalOutput = document.querySelector('[data-contract-total]');

  const rows = () => [...list.querySelectorAll('[data-milestone-row]')];
  const updateNumbers = () => {
    rows().forEach((row, index) => {
      const number = row.querySelector('[data-milestone-number]');
      if (number) number.textContent = String(index + 1).padStart(2, '0');
      const remove = row.querySelector('[data-remove-milestone]');
      if (remove) remove.hidden = rows().length <= 1;
    });
    if (totalInput) totalInput.value = rows().length;
    if (addButton) addButton.disabled = rows().length >= max;
    updateTotal();
  };

  const updateTotal = () => {
    const sum = rows().reduce((total, row) => {
      const input = row.querySelector('input[name$="-amount"]');
      const value = Number(input?.value || 0);
      return total + (Number.isFinite(value) ? value : 0);
    }, 0);
    if (totalOutput) totalOutput.textContent = sum.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
  };

  addButton?.addEventListener('click', () => {
    const index = rows().length;
    if (index >= max) return;
    const wrapper = document.createElement('fieldset');
    wrapper.className = 'milestone-editor';
    wrapper.dataset.milestoneRow = '';
    const html = emptyTemplate.innerHTML.replaceAll('__prefix__', String(index));
    wrapper.innerHTML = `<legend>Milestone <span data-milestone-number></span><button class="remove-milestone" type="button" data-remove-milestone>Remove</button></legend>${html}`;
    list.appendChild(wrapper);
    updateNumbers();
  });

  list.addEventListener('click', (event) => {
    const remove = event.target.closest('[data-remove-milestone]');
    if (!remove || rows().length <= 1) return;
    remove.closest('[data-milestone-row]').remove();
    rows().forEach((row, index) => {
      row.querySelectorAll('[name], [id], label[for]').forEach((element) => {
        for (const attribute of ['name', 'id', 'for']) {
          const value = element.getAttribute(attribute);
          if (value) element.setAttribute(attribute, value.replace(new RegExp(`${prefix}-\\d+-`), `${prefix}-${index}-`));
        }
      });
    });
    updateNumbers();
  });

  list.addEventListener('input', (event) => {
    if (event.target.matches('input[name$="-amount"]')) updateTotal();
  });
  list.addEventListener('change', (event) => {
    if (event.target.matches('input[name$="-amount"]')) updateTotal();
  });
  updateNumbers();
})();
