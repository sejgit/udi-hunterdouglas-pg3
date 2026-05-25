((python-mode
  . ((eval . (let ((venv (getenv "VIRTUAL_ENV")))
               (when (and venv (file-exists-p venv))
                 (let ((venv-name (file-name-nondirectory venv)))
                   (setq python-shell-interpreter (concat venv "/bin/python"))
                   (setq lsp-pyright-venv-path venv)
                   (setq lsp-pyright-venv-name venv-name)))))))

 (python-ts-mode
  . ((eval . (let ((venv (getenv "VIRTUAL_ENV")))
               (when (and venv (file-exists-p venv))
                 (let ((venv-name (file-name-nondirectory venv)))
                   (setq python-shell-interpreter (concat venv "/bin/python"))
                   (setq lsp-pyright-venv-path venv)
                   (setq lsp-pyright-venv-name venv-name))))))))
