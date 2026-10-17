(function () {
    // 1. 注入 CSS 样式（调整挂件摇杆粗细与颜色）
    const style = document.createElement('style');
    style.textContent = `
      #sakana-widget .sakana-widget-rod {
        width: 4px !important;
        background-color: rgba(0, 0, 0, 0.2) !important;
      }
    `;
    document.head.appendChild(style);
  
    // 2. 页面加载完成后注入 DOM 节点容器
    function injectWidgetContainer() {
      if (!document.getElementById('sakana-widget')) {
        const widgetDiv = document.createElement('div');
        widgetDiv.id = 'sakana-widget';
        widgetDiv.style.cssText = 'position: fixed; bottom: 20px; right: 20px; z-index: 9999;';
        document.body.appendChild(widgetDiv);
      }
    }
  
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', injectWidgetContainer);
    } else {
      injectWidgetContainer();
    }
  
    // 3. 定义 SakanaWidget 初始化逻辑
    window.initSakanaWidget = function () {
      if (typeof SakanaWidget === 'undefined') return;
  
      // 获取内置的千束角色数据作为模板
      const myCharacter = SakanaWidget.getCharacter('chisato');
  
      // 如果获取到了，修改它的图片链接
      if (myCharacter) {
        myCharacter.image = '/main/sakana.png'; // 换成你的透明 PNG 图片链接
      }
  
      // 注册一个名为 'my-char' 的新角色
      SakanaWidget.registerCharacter('my-char', myCharacter);
  
      // 实例化并挂载，指定默认显示这个新角色
      new SakanaWidget({
        character: 'my-char',
        imageFit: 'contain', // 保证非正方形图片能完整显示
      }).mount('#sakana-widget');
    };
  
    // 4. 动态异步加载 sakana.js 核心脚本
    const script = document.createElement('script');
    script.async = true;
    script.src = '/main/sakana.js';
    script.onload = window.initSakanaWidget;
    document.head.appendChild(script);
  })();